'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { SidebarBody, navItems } from '@/components/layout/Sidebar'

function getCurrentLabel(pathname: string) {
  const currentItem = navItems.find((item) => pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href)))
  return currentItem?.label ?? 'Job Radar'
}

export function MobileHeader() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  return (
    <>
      <header className="md:hidden border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex h-14 items-center gap-3 px-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setOpen(true)}
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="min-w-0">
            <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground/70">
              Job Radar
            </div>
            <div className="truncate text-sm font-medium text-foreground">
              {getCurrentLabel(pathname)}
            </div>
          </div>
        </div>
      </header>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="left"
          className="w-[88vw] max-w-80 gap-0 p-0"
          showCloseButton={false}
        >
          <SheetHeader className="border-b px-4 py-4">
            <SheetTitle className="text-lg font-bold tracking-tight">
              Job <span className="text-primary">Radar</span>
            </SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col">
            <SidebarBody onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}
