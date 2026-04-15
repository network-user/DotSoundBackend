import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon/Icon'

export function LegalView() {
  const navigate = useNavigate()

  return (
    <div className="legal-view">
      <div className="legal-header">
        <button
          className="icon-btn"
          onClick={() => navigate(-1)}
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <h1>Правообладателям</h1>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h2>Статус сервиса</h2>
          <p>
            DotSound является информационным посредником
            в соответствии со ст. 1253.1 Гражданского
            кодекса Российской Федерации. Сервис не
            осуществляет хранение аудиофайлов — контент
            транслируется напрямую из открытых источников
            (SoundCloud и др.). В базе данных хранятся
            исключительно метаданные: название, исполнитель,
            обложка и ссылка на оригинал.
          </p>
        </section>

        <section className="legal-section">
          <h2>Удаление контента</h2>
          <p>
            Если вы являетесь правообладателем и
            обнаружили материал, нарушающий ваши права,
            вы можете подать жалобу через форму на
            карточке трека (кнопка «Жалоба»), выбрав
            тип «Нарушение авторских прав».
          </p>
          <p>
            В жалобе укажите:
          </p>
          <ul>
            <li>Ваше имя / название организации</li>
            <li>Контактный email</li>
            <li>
              Ссылку на подтверждение прав (оригинал
              на вашем сайте, каталог дистрибьютора и т.д.)
            </li>
            <li>Описание нарушения</li>
          </ul>
          <p>
            После проверки обоснованности жалобы материал
            будет скрыт в течение 24 часов.
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
              Ст. 1301 ГК РФ — компенсация за
              нарушение авторских прав
            </li>
          </ul>
        </section>

        <section className="legal-section">
          <h2>Контакты</h2>
          <p>
            По вопросам авторских прав обращайтесь через
            форму жалобы в приложении или по email,
            указанному в настройках сервиса.
          </p>
        </section>
      </div>
    </div>
  )
}
