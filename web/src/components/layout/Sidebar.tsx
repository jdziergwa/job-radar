'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  LayoutDashboard, 
  Briefcase, 
  BarChart3, 
  Building2, 
  Settings, 
  ChevronLeft, 
  ChevronRight, 
  Moon, 
  Sun 
} from 'lucide-react'
import { useTheme } from 'next-themes'
import { Button } from '@/components/ui/button'
import { PipelineTrigger } from '@/components/pipeline/PipelineTrigger'

export const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/jobs', label: 'Job Board', icon: Briefcase },
  { href: '/stats', label: 'Market Trends', icon: BarChart3 },
  { href: '/companies', label: 'Companies', icon: Building2 },
  { href: '/settings', label: 'Settings', icon: Settings },
]

interface SidebarBodyProps {
  collapsed?: boolean
  onNavigate?: () => void
}

function ThemeToggleButton({ collapsed = false }: { collapsed?: boolean }) {
  const { theme, setTheme } = useTheme()

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="w-full flex justify-center h-10 group"
      title="Toggle Theme"
    >
      <div className="relative h-4 w-4">
        <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
        <Moon className="absolute inset-0 h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      </div>
      {!collapsed && <span className="ml-3 font-medium">Toggle Theme</span>}
    </Button>
  )
}

export function SidebarBody({ collapsed = false, onNavigate }: SidebarBodyProps) {
  const pathname = usePathname()

  return (
    <>
      <div className="p-2 border-b">
        <PipelineTrigger collapsed={collapsed} />
      </div>

      <nav className="flex-1 space-y-1 p-2 py-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              title={collapsed ? item.label : undefined}
              className={`relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-200 group ${
                isActive
                  ? 'bg-primary/10 text-foreground'
                  : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
              }`}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-primary rounded-r-full" />
              )}
              <Icon className={`h-4 w-4 flex-shrink-0 transition-transform group-hover:scale-110 ${isActive ? 'text-primary' : ''}`} />
              {!collapsed && <span className={isActive ? 'font-semibold' : ''}>{item.label}</span>}
            </Link>
          )
        })}
      </nav>

      <div className="p-2 border-t mt-auto">
        <ThemeToggleButton collapsed={collapsed} />
      </div>
    </>
  )
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside 
      className={`hidden md:flex flex-col border-r bg-background transition-all duration-300 ease-in-out ${
        collapsed ? 'w-16' : 'w-64'
      } sticky top-0 h-screen`}
    >
      <div className="flex h-14 items-center justify-between px-4 border-b">
        {!collapsed && (
          <span className="font-bold tracking-tight text-lg">
            Job <span className="text-primary">Radar</span>
          </span>
        )}
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={() => setCollapsed(!collapsed)} 
          className={`ml-auto flex-shrink-0 transition-transform duration-300 ${collapsed ? '' : 'rotate-0'}`}
          title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      <SidebarBody collapsed={collapsed} />
    </aside>
  )
}
