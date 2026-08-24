import { useEffect } from 'react'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import AppLayout from './components/AppLayout'
import AccountDetailPage from './pages/AccountDetailPage'
import MarketplacePage from './pages/MarketplacePage'
import NotificationPage from './pages/NotificationPage'
import OwnerPortalPage from './pages/OwnerPortalPage'
import PublishPage from './pages/PublishPage'
import RenterDashboardPage from './pages/RenterDashboardPage'
import VerifyPage from './pages/VerifyPage'
import { StoreProvider } from './store'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <StoreProvider>
      <BrowserRouter>
        <ScrollToTop />
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<MarketplacePage />} />
            <Route path="account/:id" element={<AccountDetailPage />} />
            <Route path="rentals" element={<RenterDashboardPage />} />
            <Route path="owner" element={<OwnerPortalPage />} />
            <Route path="owner/publish" element={<PublishPage />} />
            <Route path="owner/verify" element={<VerifyPage />} />
            <Route path="owner/notifications" element={<NotificationPage />} />
            <Route path="notifications" element={<NotificationPage />} />
            <Route path="dashboard" element={<Navigate to="/rentals" replace />} />
            <Route path="publish" element={<Navigate to="/owner/publish" replace />} />
            <Route path="verify" element={<Navigate to="/owner/verify" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  )
}
