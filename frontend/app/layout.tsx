import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import Providers from '@/components/Providers'

const interDisplay = Inter({ subsets: ['latin'], variable: '--font-display', weight: ['700', '800'] })
const interBody = Inter({ subsets: ['latin'], variable: '--font-body', weight: ['400', '500', '600', '700'] })
const jetBrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-data', weight: ['400'] })

export const metadata: Metadata = {
  title: 'Nexus — Financial Intelligence',
  description: 'Agentic AI Financial Intelligence Platform for MSMEs',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${interDisplay.variable} ${interBody.variable} ${jetBrainsMono.variable} font-body antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
