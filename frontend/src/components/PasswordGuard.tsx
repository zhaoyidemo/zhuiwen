import { useState } from 'react'
import { Lock } from 'lucide-react'
import { verifyPassword } from '../api/client'

interface Props {
  onAuth: () => void
}

export default function PasswordGuard({ onAuth }: Props) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    const ok = await verifyPassword(password)
    if (ok) {
      localStorage.setItem('site_password', password)
      onAuth()
    } else {
      setError('密码错误，请重试')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="bg-gray-800 rounded-2xl p-8 w-full max-w-sm shadow-2xl"
      >
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center">
            <Lock className="w-8 h-8 text-white" />
          </div>
        </div>
        <h1 className="text-white text-xl font-semibold text-center mb-2">继续追问</h1>
        <p className="text-gray-400 text-sm text-center mb-6">抖音数据分析平台</p>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="请输入访问密码"
          className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 mb-4"
          autoFocus
        />
        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
        <button
          type="submit"
          disabled={loading || !password}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
        >
          {loading ? '验证中...' : '进入'}
        </button>
      </form>
    </div>
  )
}
