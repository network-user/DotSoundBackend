import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  LEGAL_DOCS,
  type LegalDocId,
} from './legalContent'

export function LegalView() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const legalLinks: Array<{
    id: LegalDocId
    label: string
  }> = [
    { id: 'copyright', label: t('redesign.legal.docCopyright') },
    { id: 'terms', label: t('redesign.legal.docTerms') },
    { id: 'privacy', label: t('redesign.legal.docPrivacy') },
    { id: 'upload-rules', label: t('redesign.legal.docUploadRules') },
  ]

  return (
    <div className="legal-view">
      <div className="legal-header">
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="icon-btn"
          onClick={() => navigate(-1)}
          aria-label={t('redesign.home.back')}
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </MotionPress>
        <h1>{t('redesign.legal.title')}</h1>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h2>{t('redesign.legal.docsTitle')}</h2>
          <p>{t('redesign.legal.docsBody')}</p>
          <div className="legal-doc-list">
            {legalLinks.map((item) => (
              <MotionPress
                key={item.id}
                variant="ghost"
                haptic="selection"
                className="btn-secondary"
                onClick={() => navigate(`/legal/${item.id}`)}
              >
                {item.label}
              </MotionPress>
            ))}
          </div>
        </section>

        <section className="legal-section">
          <h2>{t('redesign.legal.statusTitle')}</h2>
          <p>{t('redesign.legal.statusBody1')}</p>
          <p>{t('redesign.legal.statusBody2')}</p>
        </section>

        <section className="legal-section">
          <h2>{t('redesign.legal.externalTitle')}</h2>
          <p>{t('redesign.legal.externalBody1')}</p>
          <p>{t('redesign.legal.externalBody2')}</p>
          <p>{t('redesign.legal.externalBody3')}</p>
        </section>

        <section className="legal-section">
          <h2>{t('redesign.legal.noticeTitle')}</h2>
          <p>{t('redesign.legal.noticeBody1')}</p>
          <p>{t('redesign.legal.noticeBody2')}</p>
          <ul>
            <li>{t('redesign.legal.noticeItem1')}</li>
            <li>{t('redesign.legal.noticeItem2')}</li>
            <li>{t('redesign.legal.noticeItem3')}</li>
            <li>{t('redesign.legal.noticeItem4')}</li>
            <li>{t('redesign.legal.noticeItem5')}</li>
          </ul>
          <p>{t('redesign.legal.noticeBody3')}</p>
        </section>

        <section className="legal-section">
          <h2>{t('redesign.legal.basisTitle')}</h2>
          <ul>
            <li>{t('redesign.legal.basisItem1')}</li>
            <li>{t('redesign.legal.basisItem2')}</li>
            <li>{t('redesign.legal.basisItem3')}</li>
            <li>{t('redesign.legal.basisItem4')}</li>
          </ul>
        </section>

        <section className="legal-section">
          <h2>{t('redesign.legal.contactsTitle')}</h2>
          <p>{t('redesign.legal.contactsBody')}</p>
        </section>

        <section className="legal-section">
          <h2>{t('redesign.legal.quickLinksTitle')}</h2>
          <ul>
            {legalLinks.map((item) => (
              <li key={item.id}>
                <MotionPress
                  variant="ghost"
                  haptic="selection"
                  className="linklike-btn"
                  onClick={() => navigate(`/legal/${item.id}`)}
                >
                  {LEGAL_DOCS[item.id].title}
                </MotionPress>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
