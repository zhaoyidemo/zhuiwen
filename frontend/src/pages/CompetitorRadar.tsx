import { useState } from 'react'
import { Plus, RefreshCw, Loader2, ArrowUpDown } from 'lucide-react'
import { addAccount, syncAccountVideos } from '../api/client'
import type { AccountData, VideoData } from '../types'
import VideoCard from '../components/VideoCard'

function formatNum(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(n)
}

const SORT_OPTIONS = [
  { value: 'collect_rate', label: '收藏率' },
  { value: 'digg_count', label: '点赞数' },
  { value: 'comment_count', label: '评论数' },
  { value: 'play_count', label: '播放量' },
  { value: 'create_time', label: '发布时间' },
]

export default function CompetitorRadar() {
  const [uniqueId, setUniqueId] = useState('')
  const [category, setCategory] = useState('竞品')
  const [accounts, setAccounts] = useState<AccountData[]>([])
  const [adding, setAdding] = useState(false)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [error, setError] = useState('')

  // 已选账号的视频
  const [selectedAccount, setSelectedAccount] = useState<AccountData | null>(null)
  const [videos, setVideos] = useState<VideoData[]>([])
  const [sortBy, setSortBy] = useState('collect_rate')

  const handleAdd = async () => {
    if (!uniqueId.trim()) return
    setAdding(true)
    setError('')
    try {
      const account = await addAccount(uniqueId.trim(), category)
      setAccounts((prev) => [...prev, account])
      setUniqueId('')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '添加失败')
    }
    setAdding(false)
  }

  const handleSync = async (account: AccountData) => {
    setSyncing(account.sec_user_id)
    setError('')
    try {
      const result = await syncAccountVideos(account.sec_user_id)
      setSelectedAccount(account)
      setVideos(result.videos || [])
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '同步失败')
    }
    setSyncing(null)
  }

  // 本地排序
  const sortedVideos = [...videos].sort((a, b) => {
    const va = (a as unknown as Record<string, unknown>)[sortBy]
    const vb = (b as unknown as Record<string, unknown>)[sortBy]
    if (typeof va === 'number' && typeof vb === 'number') return vb - va
    if (typeof va === 'string' && typeof vb === 'string') return vb.localeCompare(va)
    return 0
  })

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-1">竞品账号雷达</h2>
      <p className="text-sm text-gray-500 mb-6">
        添加竞品账号，追踪视频数据表现
      </p>

      {/* 添加账号 */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={uniqueId}
          onChange={(e) => setUniqueId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="输入抖音号 unique_id"
          className="flex-1 max-w-sm px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:border-blue-500"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-3 py-2.5 border border-gray-300 rounded-xl text-sm bg-white"
        >
          <option value="竞品">竞品</option>
          <option value="自己主号">自己主号</option>
          <option value="矩阵号">矩阵号</option>
        </select>
        <button
          onClick={handleAdd}
          disabled={adding || !uniqueId.trim()}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-xl text-sm font-medium flex items-center gap-2 transition-colors"
        >
          {adding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          添加
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">{error}</div>
      )}

      {/* 账号卡片 */}
      {accounts.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
          {accounts.map((acc) => (
            <div
              key={acc.account_id || acc.unique_id}
              className={`bg-white rounded-xl border p-4 cursor-pointer transition-all hover:shadow-md ${
                selectedAccount?.account_id === acc.account_id
                  ? 'border-blue-400 ring-2 ring-blue-100'
                  : 'border-gray-200'
              }`}
              onClick={() => setSelectedAccount(acc)}
            >
              <div className="flex items-center gap-3 mb-3">
                {acc.avatar_url ? (
                  <img src={acc.avatar_url} alt="" className="w-12 h-12 rounded-full" />
                ) : (
                  <div className="w-12 h-12 bg-gray-200 rounded-full" />
                )}
                <div className="min-w-0">
                  <p className="font-medium text-gray-800 truncate">{acc.nickname || acc.unique_id}</p>
                  <p className="text-xs text-gray-400">@{acc.unique_id}</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs mb-3">
                <div>
                  <p className="font-semibold text-gray-700">{formatNum(acc.follower_count)}</p>
                  <p className="text-gray-400">粉丝</p>
                </div>
                <div>
                  <p className="font-semibold text-gray-700">{acc.video_count}</p>
                  <p className="text-gray-400">作品</p>
                </div>
                <div>
                  <p className="font-semibold text-gray-700">{formatNum(acc.total_favorited)}</p>
                  <p className="text-gray-400">获赞</p>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span
                  className={`text-[10px] px-2 py-0.5 rounded ${
                    acc.category === '竞品'
                      ? 'bg-orange-50 text-orange-500'
                      : 'bg-blue-50 text-blue-500'
                  }`}
                >
                  {acc.category}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleSync(acc)
                  }}
                  disabled={syncing === acc.sec_user_id}
                  className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-600 disabled:text-gray-300"
                >
                  {syncing === acc.sec_user_id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3.5 h-3.5" />
                  )}
                  同步视频
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 视频列表 */}
      {selectedAccount && videos.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800">
              {selectedAccount.nickname} 的视频
              <span className="text-sm text-gray-400 font-normal ml-2">共 {videos.length} 条</span>
            </h3>
            <div className="flex items-center gap-2">
              <ArrowUpDown className="w-4 h-4 text-gray-400" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white"
              >
                {SORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-3">
            {sortedVideos.map((v) => (
              <VideoCard key={v.aweme_id} video={v} compact />
            ))}
          </div>
        </div>
      )}

      {/* 空状态 */}
      {accounts.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg mb-2">尚未添加竞品账号</p>
          <p className="text-sm">输入抖音号开始追踪</p>
        </div>
      )}
    </div>
  )
}
