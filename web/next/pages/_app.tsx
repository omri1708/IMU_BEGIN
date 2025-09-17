import type { AppProps } from 'next/app'
import '../styles/globals.css'
import { Toaster } from 'sonner'
import { useEffect } from 'react'
import { setRole } from '../lib/rbac'
import '../styles/globals.css';

export default function App({ Component, pageProps }: AppProps){
  useEffect(()=>{ const r = new URLSearchParams(location.search).get('role'); if(r) setRole(r as any) },[])
  return <>
    <Component {...pageProps} />
    <Toaster richColors closeButton position="bottom-right" />
  </>
}
