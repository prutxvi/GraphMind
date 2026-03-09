from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import networkx as nx
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()
api_key = os.getenv("NVIDIA_API_KEY")

if not api_key:
    print("⚠️ WARNING: NVIDIA_API_KEY not found in .env file!")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

G = nx.Graph()
raw_data = {"nodes": [], "links": []}

try:
    with open("data.json", "r") as f:
        raw_data = json.load(f)
    for node in raw_data["nodes"]:
        G.add_node(node["id"], group=node["group"], type=node["type"])
    for link in raw_data["links"]:
        G.add_edge(link["source"], link["target"], relation=link["value"])
    print(f"✅ Graph Loaded! {G.number_of_nodes()} Nodes.")
except:
    print("ℹ️ Starting with empty graph.")

def extract_content(response):
    try:
        if isinstance(response, list):
            if len(response) == 0: return ""
            return extract_content(response[0])
        if hasattr(response, 'choices'):
            return response.choices[0].message.content
        if isinstance(response, dict):
            if 'choices' in response: return extract_content(response['choices'])
            if 'message' in response: return response['message']['content']
        return str(response)
    except:
        return ""

def find_json(text):
    try:
        start_index = text.find('{')
        if start_index == -1: return None
        end_index = text.rfind('}')
        if end_index == -1: return None
        return text[start_index : end_index + 1]
    except:
        return None

def repair_json(json_str):
    """Attempt to fix common JSON issues from AI output."""
    if not json_str:
        return None
    try:
        # First try as-is
        json.loads(json_str)
        return json_str
    except:
        pass
    
    fixed = json_str
    # Remove trailing commas before ] or }
    fixed = re.sub(r',\s*([\]\}])', r'\1', fixed)
    # Fix unescaped newlines inside strings
    fixed = re.sub(r'(?<=")([^"]*?)\n([^"]*?)(?=")', r'\1 \2', fixed)
    # Try to close incomplete JSON
    open_braces = fixed.count('{') - fixed.count('}')
    open_brackets = fixed.count('[') - fixed.count(']')
    if open_brackets > 0:
        fixed += ']' * open_brackets
    if open_braces > 0:
        fixed += '}' * open_braces
    
    try:
        json.loads(fixed)
        print("🔧 JSON repaired successfully.")
        return fixed
    except:
        return None

@app.get("/graph-data")
def get_graph():
    return raw_data

# NEW: Detect which node the question is about
def detect_relevant_node(user_message, graph_nodes):
    """
    Finds the most relevant node based on the user's question.
    Returns node_id or None.
    """
    user_lower = user_message.lower()
    
    # Direct match: Check if any node ID appears in the question
    for node in graph_nodes:
        node_id = node["id"]
        if node_id.lower() in user_lower:
            return node_id
    
    # Partial match: Check if keywords match
    for node in graph_nodes:
        node_id_words = node["id"].lower().split()
        for word in node_id_words:
            if len(word) > 3 and word in user_lower:
                return node["id"]
    
    return None

@app.post("/chat")
async def chat_with_graph(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message", "")
        node_id = data.get("node_id")
    except:
        return {"reply": "Error: Invalid JSON."}

    # Auto-detect node if not provided
    detected_node = None
    if not node_id:
        detected_node = detect_relevant_node(user_message, raw_data["nodes"])
        if detected_node:
            node_id = detected_node

    context_text = ""
    if node_id and node_id in G:
        neighbors = []
        for neighbor in G.neighbors(node_id):
            edge_data = G.get_edge_data(node_id, neighbor)
            relation = edge_data.get("relation", "connected_to")
            neighbors.append(f"- {node_id} {relation} {neighbor}")
        context_text = f"Focus Node: {node_id}\nConnections:\n" + "\n".join(neighbors)
    else:
        # Provide richer context when no node is selected
        node_list = [f"{n['id']} ({n['group']})" for n in raw_data["nodes"][:20]]
        context_text = f"Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.\nSample nodes: {', '.join(node_list)}"

    system_prompt = "You are GraphMind. Answer based strictly on the Context provided. Be concise and accurate."
    prompt = f"Context:\n{context_text}\n\nUser Question: {user_message}"

    try:
        completion = client.chat.completions.create(
            model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=300
        )
        
        raw_reply = extract_content(completion)
        
        # Extract thinking process if present
        thinking = ""
        reply = raw_reply
        think_match = re.search(r'<think>(.*?)</think>', raw_reply, flags=re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()
            reply = re.sub(r'<think>.*?</think>', '', raw_reply, flags=re.DOTALL).strip()
        
        return {
            "reply": reply,
            "thinking": thinking,
            "focused_node": detected_node  # Tell frontend which node to focus on
        }

    except Exception as e:
        return {"reply": f"Error connecting to AI: {str(e)}", "thinking": "", "focused_node": None}

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    global raw_data
    try:
        reader = PdfReader(file.file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        
        text = text.strip()
        if not text:
            return {"status": "error", "message": "No text found in PDF."}

        print(f"📄 Text Read ({len(text)} chars). Sending to AI...")

        system_prompt = """CRITICAL: You are a JSON-only API. Output raw JSON and NOTHING else.
Do NOT use <think> tags. Do NOT explain. Do NOT add any text before or after the JSON.
Your ENTIRE response must be a single valid JSON object.

Task: Extract a COMPREHENSIVE knowledge graph (25-50 nodes) from the text.

Rules:
- Extract: concepts, people, organizations, places, events, methods, processes, properties
- Use SPECIFIC relationship verbs: "invented_by", "part_of", "causes", "used_in", "located_in", "influences", "contains", "type_of", "preceded_by", etc.
- Build MULTI-LEVEL depth: Main Topic > Sub-topics > Details > Properties
- Groups: Person, Concept, Technology, Place, Event, Method, Organization, Property
- Use ONLY simple ASCII characters in all string values. No special quotes or unicode.

JSON format:
{"nodes": [{"id": "Name", "group": "Category", "type": "SubCategory"}], "links": [{"source": "Name", "target": "Name", "value": "relationship"}]}"""

        new_data = None
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 Attempt {attempt + 1}/{max_retries}...")
                completion = client.chat.completions.create(
                    model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Output ONLY JSON. Extract 25-50 nodes from:\n\n{text[:6000]}"}
                    ],
                    temperature=0.1 if attempt == 0 else 0.05,
                    max_tokens=4096
                )

                ai_response = extract_content(completion)
                # Aggressively strip think tags
                ai_response = re.sub(r'<think>.*?</think>', '', ai_response, flags=re.DOTALL).strip()
                ai_response = re.sub(r'</?think>', '', ai_response).strip()
                # Strip any markdown code fences
                ai_response = re.sub(r'^```json\s*', '', ai_response)
                ai_response = re.sub(r'^```\s*', '', ai_response)
                ai_response = re.sub(r'\s*```$', '', ai_response)
                
                clean_json_str = find_json(ai_response)
                
                if not clean_json_str:
                    print(f"❌ Attempt {attempt + 1}: No JSON found. Raw: {ai_response[:200]}...")
                    continue

                print(f"🤖 JSON Found: {clean_json_str[:60]}...")

                # Try direct parse first, then repair
                try:
                    new_data = json.loads(clean_json_str)
                except json.JSONDecodeError:
                    repaired = repair_json(clean_json_str)
                    if repaired:
                        new_data = json.loads(repaired)
                    else:
                        print(f"❌ Attempt {attempt + 1}: JSON parse failed even after repair.")
                        continue
                
                # Validate structure
                if "nodes" in new_data and "links" in new_data:
                    print(f"✅ Valid graph data on attempt {attempt + 1}!")
                    break
                else:
                    print(f"❌ Attempt {attempt + 1}: Missing nodes or links keys.")
                    new_data = None
                    continue
                    
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} error: {e}")
                continue
        
        if not new_data:
            return {"status": "error", "message": "AI failed to generate valid graph data after retries. Try a different PDF."}

        # Clear the existing graph completely
        G.clear()
        raw_data = {"nodes": [], "links": []}
        print("🧹 Previous graph cleared.")

        count = 0
        for node in new_data.get("nodes", []):
            node_id = node.get("id", "")
            node_group = node.get("group", "Unknown")
            node_type = node.get("type", node_group)
            if node_id:
                G.add_node(node_id, group=node_group, type=node_type)
                raw_data["nodes"].append({"id": node_id, "group": node_group, "type": node_type})
                count += 1

        for link in new_data.get("links", []):
            src = link.get("source", "")
            tgt = link.get("target", "")
            val = link.get("value", "connected_to")
            if src and tgt:
                G.add_edge(src, tgt, relation=val)
                raw_data["links"].append({"source": src, "target": tgt, "value": val})

        # Save to data.json so the graph persists across restarts
        with open("data.json", "w") as f:
            json.dump(raw_data, f, indent=2)

        print(f"✅ Success! Fresh graph with {count} nodes created.")
        return {"status": "success", "new_nodes": count}

    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/analyze")
def analyze_graph():
    """AI-powered graph analysis using NetworkX metrics + LLM insights."""
    if G.number_of_nodes() == 0:
        return {"status": "empty", "message": "No graph data to analyze. Upload a PDF first."}

    # --- NetworkX Analytics ---
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()
    density = round(nx.density(G), 4)

    # Degree centrality — find hub nodes
    degree_cent = nx.degree_centrality(G)
    top_hubs = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:5]
    hub_nodes = [{"id": n, "centrality": round(c, 3), "connections": G.degree(n)} for n, c in top_hubs]

    # Clusters / Connected components
    components = list(nx.connected_components(G))
    num_clusters = len(components)
    largest_cluster = max(len(c) for c in components) if components else 0

    # Isolated nodes (no connections)
    isolated = list(nx.isolates(G))

    # Betweenness centrality — bridge nodes
    betweenness = nx.betweenness_centrality(G)
    top_bridges = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:3]
    bridge_nodes = [{"id": n, "score": round(s, 3)} for n, s in top_bridges if s > 0]

    # Group distribution
    groups = {}
    for node in raw_data["nodes"]:
        g = node.get("group", "Unknown")
        groups[g] = groups.get(g, 0) + 1

    # All relationships
    relationships = []
    for link in raw_data["links"]:
        src = link.get("source", "")
        tgt = link.get("target", "")
        val = link.get("value", "connected_to")
        # Handle both string and dict sources (force-graph mutates these)
        if isinstance(src, dict): src = src.get("id", "")
        if isinstance(tgt, dict): tgt = tgt.get("id", "")
        relationships.append(f"{src} --[{val}]--> {tgt}")

    stats = {
        "total_nodes": num_nodes,
        "total_edges": num_edges,
        "density": density,
        "num_clusters": num_clusters,
        "largest_cluster_size": largest_cluster,
        "isolated_nodes": isolated[:10],
        "hub_nodes": hub_nodes,
        "bridge_nodes": bridge_nodes,
        "group_distribution": groups,
    }

    # --- AI Analysis ---
    analysis_context = f"""Knowledge Graph Statistics:
- Nodes: {num_nodes}, Edges: {num_edges}, Density: {density}
- Clusters: {num_clusters}, Largest cluster: {largest_cluster} nodes
- Isolated concepts: {', '.join(isolated[:5]) if isolated else 'None'}
- Hub nodes (most connected): {', '.join([f"{h['id']}({h['connections']} links)" for h in hub_nodes])}
- Bridge nodes (connect clusters): {', '.join([f"{b['id']}(score:{b['score']})" for b in bridge_nodes]) if bridge_nodes else 'None'}
- Categories: {json.dumps(groups)}
- Key relationships: {'; '.join(relationships[:20])}"""

    ai_summary = ""
    try:
        completion = client.chat.completions.create(
            model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
            messages=[
                {"role": "system", "content": "You are GraphMind AI Analyst. Given knowledge graph statistics, provide a brief, insightful analysis in 4-6 bullet points using markdown. Highlight: key themes, important hub concepts, knowledge gaps (isolated nodes), and interesting patterns. Be concise and smart."},
                {"role": "user", "content": analysis_context}
            ],
            temperature=0.5,
            max_tokens=500
        )
        raw_summary = extract_content(completion)
        ai_summary = re.sub(r'<think>.*?</think>', '', raw_summary, flags=re.DOTALL).strip()
    except Exception as e:
        ai_summary = f"AI analysis unavailable: {str(e)}"

    stats["ai_summary"] = ai_summary
    stats["status"] = "success"
    return stats

# --- Serve Frontend (Production) ---
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    print(f"🌐 Serving frontend from {static_dir}")
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend SPA - catch all non-API routes."""
        file_path = static_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")


