import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'
import { useBrandLabel } from '@/lib/brand'
import { usePageSeo } from '@/lib/pageSeo'
import {
  LEGAL_DOCS,
  type LegalDocId,
} from './legalContent'

function LegalDocBody({
  docId,
  document,
}: {
  docId: string
  document: (typeof LEGAL_DOCS)[LegalDocId]
}) {
  const navigate = useNavigate()
  const brandLabel = useBrandLabel()
  const intro = (document.intro || '').trim()

  usePageSeo({
    title: `${document.title} - ${brandLabel}`,
    description: intro ? intro.slice(0, 160) : document.title,
    path: `/legal/${docId}`,
  })

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

export function LegalDocView() {
  const { docId } = useParams()
  const document = docId
    ? LEGAL_DOCS[docId as LegalDocId]
    : null

  if (!docId || !document) {
    return <Navigate to="/legal" replace />
  }

  return <LegalDocBody docId={docId} document={document} />
}
