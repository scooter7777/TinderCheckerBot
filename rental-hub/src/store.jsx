import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import {
  fallbackCover,
  initialAccounts,
  initialNotifications,
  initialOrders,
  initialTasks,
  makeId,
} from './data'

const STORAGE_KEY = 'rental-hub-state-v3'

const StoreContext = createContext(null)

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed && Array.isArray(parsed.accounts) && parsed.accounts.length) {
        return { ...parsed, role: 'renter' }
      }
    }
  } catch (error) {
    console.warn('Failed to load rental hub state', error)
  }
  return {
    accounts: initialAccounts,
    orders: initialOrders,
    notifications: initialNotifications,
    tasks: initialTasks,
    role: 'renter',
  }
}

export function StoreProvider({ children }) {
  const [state, setState] = useState(loadState)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])

  const value = useMemo(() => {
    const pushNotification = (notification, prev) => {
      const source = prev ?? state
      return [notification, ...source.notifications].slice(0, 30)
    }

    const setRole = (role) => setState((prev) => ({ ...prev, role }))

    const markAllRead = () =>
      setState((prev) => ({
        ...prev,
        notifications: prev.notifications.map((item) => ({ ...item, read: true })),
      }))

    const markNotificationRead = (id) =>
      setState((prev) => ({
        ...prev,
        notifications: prev.notifications.map((item) =>
          item.id === id ? { ...item, read: true } : item,
        ),
      }))

    const rentAccount = ({ accountId, mode, units, amount, startLabel, remainingMin }) =>
      setState((prev) => {
        const order = {
          id: makeId('ord'),
          accountId,
          mode,
          units,
          amount,
          status: 'active',
          started: startLabel,
          remainingMin,
        }
        const account = prev.accounts.find((item) => item.id === accountId)
        const notification = {
          id: makeId('n'),
          type: 'order',
          severity: 'normal',
          title: 'Rental started',
          message: `"${account?.title ?? 'Account'}" is now active. Login credentials were sent to your order details.`,
          time: 'Just now',
          read: false,
          accountId,
          action: 'order',
        }
        return {
          ...prev,
          orders: [order, ...prev.orders],
          notifications: pushNotification(notification, prev),
        }
      })

    const publishAccount = (form) =>
      setState((prev) => {
        const account = {
          id: makeId('acc'),
          platform: form.platform,
          title: form.title,
          subtitle: form.subtitle || 'Newly listed account',
          priceHour: Number(form.priceHour) || 0,
          priceDay: Number(form.priceDay) || 0,
          rating: 5,
          reviews: 0,
          rentCount: 0,
          tier: form.tier || 'B',
          tags: form.tags,
          games: form.games,
          image: form.cover || fallbackCover[form.platform],
          owner: 'My account',
          verified: true,
          stock: Number(form.stock) || 1,
          deposit: Number(form.deposit) || 0,
          insured: form.insured,
          status: 'online',
          featured: false,
          badge: 'New',
          description: form.description || '',
          features: form.features,
          specs: form.specs || {},
        }
        const notification = {
          id: makeId('n'),
          type: 'system',
          severity: 'normal',
          title: 'Account listed',
          message: `"${account.title}" passed review and is now live on the marketplace.`,
          time: 'Just now',
          read: false,
          accountId: account.id,
          action: 'none',
        }
        return {
          ...prev,
          accounts: [account, ...prev.accounts],
          notifications: pushNotification(notification, prev),
        }
      })

    const resolveTask = (taskId) =>
      setState((prev) => {
        const task = prev.tasks.find((item) => item.id === taskId)
        const account = prev.accounts.find((item) => item.id === task?.accountId)
        const notification = {
          id: makeId('n'),
          type: 'system',
          severity: 'normal',
          title: task?.kind === 'ban_risk' ? 'Account risk cleared' : 'Human verification completed',
          message: `"${account?.title ?? 'Account'}" is back online for rent.`,
          time: 'Just now',
          read: false,
          accountId: task?.accountId,
          action: 'none',
        }
        return {
          ...prev,
          tasks: prev.tasks.filter((item) => item.id !== taskId),
          accounts: prev.accounts.map((item) =>
            item.id === task?.accountId ? { ...item, status: 'online', badge: '' } : item,
          ),
          notifications: pushNotification(notification, prev),
        }
      })

    const simulateEvent = () =>
      setState((prev) => {
        const occupied = new Set(prev.tasks.map((item) => item.accountId))
        const candidates = prev.accounts.filter(
          (item) => !occupied.has(item.id) && item.status !== 'risk',
        )
        if (!candidates.length) {
          return prev
        }
        const account = candidates[Math.floor(Math.random() * candidates.length)]
        const kind = Math.random() > 0.45 ? 'verify' : 'ban_risk'
        const task = {
          id: makeId('t'),
          accountId: account.id,
          kind,
          title: kind === 'verify' ? 'Human verification' : 'Ban risk review',
          channel: kind === 'verify' ? 'Email code' : 'Security center',
          reason: kind === 'verify' ? 'Platform verification triggered' : 'Multiple logins triggered risk control',
          deadlineMin: 25 + Math.floor(Math.random() * 40),
          status: 'pending',
          steps:
            kind === 'verify'
              ? ['Platform emailed a 6-digit code', 'Enter the code and confirm this sign-in', 'Account goes live again after verification']
              : ['Confirm active devices in platform security center', 'Close unknown sessions and enable login protection', 'Confirm account is safe to relist'],
        }
        const notification = {
          id: makeId('n'),
          type: kind === 'verify' ? 'verify' : 'ban_risk',
          severity: kind === 'verify' ? 'urgent' : 'high',
          title: kind === 'verify' ? `${account.title} needs human verification` : `${account.title} flagged for ban risk`,
          message:
            kind === 'verify'
              ? `"${account.title}" triggered human verification. Please handle it before the countdown ends.`
              : `"${account.title}" triggered risk control. Renting is paused; confirm account safety.`,
          time: 'Just now',
          read: false,
          accountId: account.id,
          action: 'verify',
        }
        return {
          ...prev,
          tasks: [task, ...prev.tasks],
          accounts: prev.accounts.map((item) =>
            item.id === account.id ? { ...item, status: 'risk', badge: 'Verify now' } : item,
          ),
          notifications: pushNotification(notification, prev),
        }
      })

    return {
      ...state,
      setRole,
      markAllRead,
      markNotificationRead,
      rentAccount,
      publishAccount,
      resolveTask,
      simulateEvent,
    }
  }, [state])

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}

export function useStore() {
  const context = useContext(StoreContext)
  if (!context) {
    throw new Error('useStore must be used inside StoreProvider')
  }
  return context
}
