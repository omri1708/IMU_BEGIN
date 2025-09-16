import type { AppProps } from 'next/app'
import { useEffect } from 'react'
import { setRole } from '../lib/rbac'

export default function App({ Component, pageProps }: AppProps) {
  // מאפשר לבחור Role דרך פרמטר כתובת: ?role=user|manager|admin
  useEffect(() => {
    const p = new URLSearchParams(window.location.search)
    const r = p.get('role')
    if (r) setRole(r as any)
  }, [])

  return <Component {...pageProps} />
}
