import { Brain } from 'lucide-react'

export default function AIAnalysis() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center text-gray-400">
        <Brain className="w-16 h-16 mx-auto mb-4 text-gray-300" />
        <h2 className="text-xl font-semibold text-gray-600 mb-2">AI 分析助手</h2>
        <p className="text-sm">V2 版本开放，敬请期待</p>
        <p className="text-xs mt-4 text-gray-300">
          功能预告：爆款模式分析 · 竞品对比报告 · 跨平台文案改写
        </p>
      </div>
    </div>
  )
}
