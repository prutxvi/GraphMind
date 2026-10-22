import { useEffect } from 'react';

export default function Method() {
  useEffect(() => { document.title = 'How Footnote works · Footnote'; }, []);
  return (
    <main className="wrap page">
      <article className="prose">
        <div className="kicker">Method</div>
        <h1 className="h1" style={{ marginBottom: 16 }}>How Footnote reads a filing</h1>
        <p>
          An Indian IPO offer document (DRHP, RHP or prospectus) runs 300 to 800 pages. Most of what tells you who benefits
          from the company sits in a handful of sections. Footnote reads those, links what it finds, and keeps the page for every line.
        </p>

        <h2 className="h2">1. Find the sections</h2>
        <p>
          Footnote reads the filing's own table of contents, works out how printed page numbers map to PDF pages, and opens:
          General Information, Our Management, Our Promoters and Promoter Group, Group Companies, the related-party
          transactions summary (or the related-party note in the restated financials), Objects of the Issue, Outstanding
          Litigation, and the summary financials. A 460-page filing becomes about 60 pages.
        </p>

        <h2 className="h2">2. Extract fixed fields, with quotes</h2>
        <p>
          A language model reads each section and fills a fixed form: names, DINs, shareholding, adviser registrations,
          related-party amounts and the percentage of revenue, cases by type. It must copy a short verbatim quote for every
          item. Footnote then searches the page for that quote. If it is not there word for word, the item is marked
          <strong> unverified</strong> and shown with a warning, never silently trusted.
        </p>

        <h2 className="h2">3. Link people and companies</h2>
        <p>
          People are linked across filings only by DIN, because names collide. Companies are linked by CIN, SEBI or firm
          registration number, or a normalised name. Personal identifiers such as PAN, Aadhaar and home addresses are never
          stored or shown, even when the filing prints them.
        </p>

        <h2 className="h2">4. Run fixed checks</h2>
        <ul>
          <li><strong>Business with related companies.</strong> Sales, purchases, services and rent with related companies as a share of revenue in the latest year. Flagged above 3%, and strongly above 10%.</li>
          <li><strong>Money lent to related parties.</strong> Loans or advances given to promoters, directors or their companies.</li>
          <li><strong>IPO money to related parties.</strong> Any part of the proceeds planned for promoters, directors or group companies. A clear statement that none is planned shows as reassuring.</li>
          <li><strong>Auditor resigned.</strong> Any resignation of the statutory auditor in the last three years, with the stated reason.</li>
          <li><strong>Pending cases.</strong> Criminal and regulatory cases against the company, promoters and directors, as disclosed.</li>
          <li><strong>Lead manager's record.</strong> Other filings the same merchant banker handled, and any SEBI orders naming it, from a hand-checked list.</li>
          <li><strong>Profit without cash.</strong> A reported profit while operations used cash in the same year.</li>
        </ul>
        <p>These are rules over what the company itself disclosed. No model decides whether something is suspicious.</p>

        <h2 className="h2">What Footnote is not</h2>
        <p>
          A flag is a reason to read the page, not proof of wrongdoing. Related-party transactions are legal and often normal.
          Footnote is not investment advice and does not say whether to apply for an IPO. Extraction can miss or misread
          items, which is why every line links to its page. If you find a mistake, report it and it will be fixed.
        </p>
        <h2 className="h2">Sources</h2>
        <p>Offer documents filed with SEBI and the stock exchanges, downloaded by hand in line with each site's terms.</p>
      </article>
    </main>
  );
}
