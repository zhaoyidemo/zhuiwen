import { BarChart3 } from 'lucide-react'

export default function Dashboard() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center text-gray-400">
        <BarChart3 className="w-16 h-16 mx-auto mb-4 text-gray-300" />
        <h2 className="text-xl font-semibold text-gray-600 mb-2">作战仪表盘</h2>
        <p className="text-sm">V2 版本开放，敬请期待</p>
        <p className="text-xs mt-4 text-gray-300">
          功能预告：自己账号绑定 · 北极星指标趋势 · 矩阵号 A/B 对比
        </p>
      </div>
    </div>
  )
}
