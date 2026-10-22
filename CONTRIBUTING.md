# Contributing to Footnote

Thank you for your interest in contributing to Footnote! We welcome contributions from the community. This document provides guidelines and instructions for getting started.

## 📋 Code of Conduct

Be respectful, inclusive, and professional. We're committed to providing a welcoming and harassment-free environment for all contributors.

## 🐛 Reporting Issues

Found a bug? Please open an issue with:
- **Clear title** describing the problem
- **Detailed description** of the issue
- **Steps to reproduce** the problem
- **Expected vs actual behavior**
- **Your environment** (OS, Python version, Node version)
- **Screenshots or logs** if applicable

Example:
```
Title: PDF upload fails with "Expecting value" error

Steps:
1. Upload a valid PDF
2. Check backend logs

Expected: JSON extracted successfully
Actual: "Expecting value: line 1 column 1" error
```

## 💡 Suggesting Enhancements

Want to suggest a new feature? Open an issue with:
- **Feature description** – what should it do?
- **Motivation** – why is this useful?
- **Possible implementation** – how might it work?
- **Alternative approaches** – any other ways to solve this?

## 🔄 Pull Request Process

### 1. Fork & Clone
```bash
git clone https://github.com/prutxvi/Footnote.git
cd Footnote
git checkout -b feature/your-feature-name
```

### 2. Set Up Development Environment

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key
```

**Frontend:**
```bash
cd frontend
npm install
```

### 3. Make Your Changes

- Keep commits atomic and well-documented
- Follow the coding style of the project
- Add tests for new features
- Update documentation as needed

### 4. Test Your Changes

**Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
# Test manually or use curl/Postman
```

**Frontend:**
```bash
cd frontend
npm run dev
npm run lint  # Check for linting errors
```

### 5. Commit & Push

```bash
git add .
git commit -m "Add: descriptive commit message"
git push origin feature/your-feature-name
```

Use clear commit messages:
- `Add: new feature description`
- `Fix: bug description`
- `Refactor: code area being refactored`
- `Docs: documentation update`
- `Test: test addition or fix`

### 6. Open a Pull Request

- Reference any related issues: `Fixes #123`
- Describe what changes you made and why
- Include screenshots for UI changes
- Ensure all CI checks pass

Example PR description:
```markdown
## Description
Added PDF parsing improvements to handle malformed JSON responses from AI.

## Changes
- Strip `<think>` tags before JSON parsing
- Implement robust JSON extraction from mixed content
- Add debug logging for parsing failures

## Type of Change
- [x] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change

## Testing
Tested with:
- Valid PDFs with proper text extraction
- Malformed PDFs
- PDFs with embedded images

## Screenshots
[If UI changes]
```

## 📝 Coding Standards

### Python (Backend)
- Follow [PEP 8](https://pep8.org/)
- Use type hints for function parameters and returns
- Write docstrings for functions and classes
- Use meaningful variable names

Example:
```python
def extract_json_from_response(response: str) -> dict:
    """Extract JSON object from AI response, handling markdown fences."""
    # Implementation
    return parsed_json
```

### JavaScript/React (Frontend)
- Use consistent naming (camelCase for variables/functions)
- Comment complex logic
- Use functional components with hooks
- Keep components focused and modular

Example:
```javascript
function ChatMessage({ message, sender, thought }) {
  // Component implementation
}
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm test
```

Please add tests for new features and bug fixes.

## 📚 Documentation

- Update README.md if you add new features
- Add docstrings to new functions/classes
- Comment non-obvious logic
- Include examples in complex features

## 🎯 Contribution Areas

We welcome contributions in:

### High Priority
- Performance optimizations
- Bug fixes
- Documentation improvements
- Test coverage

### Medium Priority
- New visualization options
- UI/UX improvements
- Additional LLM provider support
- Advanced query features

### Nice to Have
- Additional example datasets
- Docker setup
- CI/CD improvements
- Plugin system

## 📞 Questions?

- Check existing issues and discussions
- Review the documentation in README.md
- Open a discussion for general questions
- Join our community (if applicable)

## 🙏 Thank You

Your contributions make Footnote better for everyone. Thank you for helping!

---

**Happy Contributing! 🚀**
