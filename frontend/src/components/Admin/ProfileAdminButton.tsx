import { useNavigate } from 'react-router-dom'
import { useAdminMenu } from './AdminContext'

export function ProfileAdminButton() {
  const menu = useAdminMenu()
  const navigate = useNavigate()
  const entry = menu[0]
  if (!entry) return null
  return (
    <button
      className="profile-admin-btn"
      onClick={() => navigate(entry.route)}
    >
      {entry.label}
    </button>
  )
}
