import { NavLink, Outlet } from 'react-router-dom'
import { Video, Radar, BarChart3, Brain } from 'lucide-react'

const navItems = [
  { to: '/', icon: Video, label: '视频解剖台', badge: '' },
  { to: '/competitor', icon: Radar, label: '竞品雷达', badge: '' },
  { to: '/dashboard', icon: BarChart3, label: '作战仪表盘', badge: 'V2' },
  { to: '/analysis', icon: Brain, label: 'AI 分析', badge: 'V2' },
]

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* 侧边栏 */}
      <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col shrink-0">
        <div className="p-5 border-b border-gray-700">
          <h1 className="text-lg font-bold text-white leading-tight">继续追问</h1>
          <p className="text-xs text-gray-500 mt-1">抖音数据分析平台</p>
        </div>

        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label, badge }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'hover:bg-gray-800 text-gray-400'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
              {badge && (
                <span className="ml-auto text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded">
                  {badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-700 text-xs text-gray-600">
          v1.0.0 · 赵翼
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
