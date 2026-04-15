import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import {
  LEGAL_DOCS,
  type LegalDocId,
} from './legalContent'

export function LegalDocView() {
  const navigate = useNavigate()
  const { docId } = useParams()
  const document = docId
    ? LEGAL_DOCS[docId as LegalDocId]
    : null

  if (!document) {
    return <Navigate to="/legal" replace />
  }

  return (
    <div className="legal-view">
      <div className="legal-header">
        <button
          className="icon-btn"
          onClick={() => navigate(-1)}
        >
          <Icon
            name="chevron"
            size={20}
            className="back-chevron"
          />
        </button>
        <h1>{document.title}</h1>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <p>{document.intro}</p>
        </section>
        {document.sections.map((section) => (
          <section
            key={section.title}
            className="legal-section"
          >
            <h2>{section.title}</h2>
            {section.paragraphs?.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
            {section.bullets && (
              <ul>
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </div>
  )
}
