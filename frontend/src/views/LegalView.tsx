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
    { id: 'copyright', label: 'Правообладателям' },
    { id: 'terms', label: 'Пользовательское соглашение' },
    { id: 'privacy', label: 'Политика данных' },
    { id: 'upload-rules', label: 'Правила загрузки' },
  ]

  return (
    <div className="legal-view">
      <div className="legal-header">
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="icon-btn"
          onClick={() => navigate(-1)}
          aria-label={t('redesign.backAria', 'Back')}
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </MotionPress>
        <h1>{t('redesign.legal.title', 'Правообладателям')}</h1>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h2>Юридические документы</h2>
          <p>
            В приложении доступны основные документы, которые
            объясняют модель контента, жалоб, пользовательской
            загрузки и обработки данных.
          </p>
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
          <h2>Статус сервиса</h2>
          <p>
            DotSound стремится действовать в модели
            информационного посредника в соответствии
            со ст. 1253.1 ГК РФ. В сервисе могут
            присутствовать пользовательские материалы,
            размещённые пользователями DotSound, а также
            внешние треки, для которых DotSound хранит
            метаданные и ссылку на оригинальный источник.
          </p>
          <p>
            Для пользовательских загрузок аудиофайл может
            размещаться в инфраструктуре DotSound. Для
            внешних треков DotSound не должен
            позиционировать себя как правообладатель и
            обязан явно показывать источник материала.
          </p>
        </section>

        <section className="legal-section">
          <h2>Внешние источники</h2>
          <p>
            Для внешних треков DotSound хранит сведения
            об источнике и ссылку на оригинальный
            материал. Такие треки должны сопровождаться
            указанием источника и ссылкой на оригинал.
          </p>
          <p>
            В текущем MVP для отдельных внешних треков
            доступ может предоставляться через поток
            стороннего сервиса внутри интерфейса
            DotSound без копирования аудиофайла в
            инфраструктуру DotSound.
          </p>
          <p>
            Если доступ к внешнему треку предоставлен с
            нарушением прав, правообладатель может
            направить уведомление для ограничения доступа
            к карточке трека, метаданным и иной
            информации, необходимой для его получения.
          </p>
        </section>

        <section className="legal-section">
          <h2>Уведомление правообладателя</h2>
          <p>
            Если вы являетесь правообладателем или
            представителем правообладателя, используйте
            кнопку «Жалоба» на карточке трека и выберите
            тип обращения «Авторские права» или
            «Смежные права».
          </p>
          <p>
            В уведомлении укажите:
          </p>
          <ul>
            <li>имя правообладателя или представителя</li>
            <li>контактный e-mail</li>
            <li>
              ссылку на подтверждение прав
              (официальный сайт, карточка дистрибьютора,
              каталог лейбла и т.д.)
            </li>
            <li>ссылку на страницу трека в DotSound</li>
            <li>описание нарушения</li>
          </ul>
          <p>
            После получения надлежаще оформленного
            уведомления DotSound проводит проверку и
            принимает меры по ограничению доступа или
            удалению спорной информации в сроки,
            предусмотренные применимым законодательством.
          </p>
        </section>

        <section className="legal-section">
          <h2>Правовая основа</h2>
          <ul>
            <li>
              Ст. 1253.1 ГК РФ — ответственность
              информационного посредника
            </li>
            <li>
              Ст. 1270 ГК РФ — использование произведения
            </li>
            <li>
              Ст. 1301 ГК РФ — компенсация за
              нарушение авторских прав
            </li>
            <li>
              Ст. 15.7 149-ФЗ — внесудебные меры по
              прекращению нарушения авторских и смежных
              прав в сети Интернет
            </li>
          </ul>
        </section>

        <section className="legal-section">
          <h2>Контакты</h2>
          <p>
            По вопросам авторских и смежных прав
            направляйте обращение через форму жалобы в
            приложении. Публичные юридические тексты и
            внутренняя правовая матрица сервиса
            синхронизируются с фактической архитектурой
            проекта и порядком модерации.
          </p>
        </section>

        <section className="legal-section">
          <h2>Краткие ссылки</h2>
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
