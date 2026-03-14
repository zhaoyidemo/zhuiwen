import { useState } from 'react'
import { Search, Loader2, Play, Heart, MessageCircle, Bookmark, Share2, Download, Music, CheckCircle } from 'lucide-react'
import { parseVideo } from '../api/client'
import type { VideoData } from '../types'

function formatNum(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return n.toLocaleString()
  return String(n)
}

function formatRate(rate: number): string {
  return (rate * 100).toFixed(2) + '%'
}

function rateColorClass(rate: number): string {
  if (rate >= 0.05) return 'text-red-500'
  if (rate >= 0.03) return 'text-amber-500'
  return 'text-emerald-500'
}

function rateBgClass(rate: number): string {
  if (rate >= 0.05) return 'bg-red-50 border-red-200'
  if (rate >= 0.03) return 'bg-amber-50 border-amber-200'
  return 'bg-emerald-50 border-emerald-200'
}

export default function VideoAnalyzer() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [video, setVideo] = useState<VideoData | null>(null)

  const handleParse = async () => {
    if (!url.trim()) return
    setLoading(true)
    setError('')
    setVideo(null)
    try {
      const data = await parseVideo(url.trim())
      setVideo(data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '解析失败'
      setError(msg)
    }
    setLoading(false)
  }

  const stats = video
    ? [
        { icon: Play, value: video.play_count, label: '播放量', color: 'text-blue-600' },
        { icon: Heart, value: video.digg_count, label: '点赞数', color: 'text-pink-500' },
        { icon: MessageCircle, value: video.comment_count, label: '评论数', color: 'text-orange-500' },
        { icon: Bookmark, value: video.collect_count, label: '收藏数', color: 'text-yellow-500' },
        { icon: Share2, value: video.share_count, label: '转发数', color: 'text-green-500' },
      ]
    : []

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-1">视频解剖台</h2>
      <p className="text-sm text-gray-500 mb-6">
        粘贴抖音视频链接，一键获取完整数据
      </p>

      {/* 搜索栏 */}
      <div className="flex gap-3 mb-8">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleParse()}
          placeholder="粘贴抖音视频链接（支持 v.douyin.com 短链和完整链接）"
          className="flex-1 px-4 py-3 border border-gray-300 rounded-xl text-sm focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        />
        <button
          onClick={handleParse}
          disabled={loading || !url.trim()}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-xl font-medium flex items-center gap-2 transition-colors"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Search className="w-4 h-4" />
          )}
          解析
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          {error}
        </div>
      )}

      {/* 解析结果 */}
      {video && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex flex-col md:flex-row">
            {/* 封面 */}
            <div className="md:w-72 shrink-0 bg-black flex items-center justify-center">
              {video.cover_url ? (
                <img src={video.cover_url} alt="" className="w-full h-full object-contain max-h-96" />
              ) : (
                <div className="text-gray-500 text-sm py-20">暂无封面</div>
              )}
            </div>

            {/* 信息区 */}
            <div className="flex-1 p-6">
              {/* 作者 */}
              <div className="flex items-center gap-3 mb-4">
                {video.author_avatar && (
                  <img src={video.author_avatar} alt="" className="w-10 h-10 rounded-full" />
                )}
                <div>
                  <p className="font-medium text-gray-800">{video.author_nickname || '未知作者'}</p>
                  <p className="text-xs text-gray-400">
                    @{video.author_unique_id}
                    {video.author_follower_count ? ` · ${formatNum(video.author_follower_count)} 粉丝` : ''}
                  </p>
                </div>
              </div>

              {/* 描述 */}
              <p className="text-gray-700 text-sm leading-relaxed mb-4">{video.desc || '(无描述)'}</p>

              {/* 收藏率 — 最大高亮 */}
              <div className={`rounded-xl border p-4 mb-4 ${rateBgClass(video.collect_rate)}`}>
                <p className="text-xs text-gray-500 mb-1">收藏率（北极星指标）</p>
                <p className={`text-3xl font-bold tabular-nums ${rateColorClass(video.collect_rate)}`}>
                  {formatRate(video.collect_rate)}
                </p>
              </div>

              {/* 互动数据网格 */}
              <div className="grid grid-cols-5 gap-3 mb-4">
                {stats.map(({ icon: Icon, value, label, color }) => (
                  <div key={label} className="text-center p-2 bg-gray-50 rounded-lg">
                    <Icon className={`w-4 h-4 mx-auto mb-1 ${color}`} />
                    <p className="text-sm font-semibold text-gray-800 tabular-nums">{formatNum(value)}</p>
                    <p className="text-[10px] text-gray-400">{label}</p>
                  </div>
                ))}
              </div>

              {/* 元信息 */}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400 mb-4">
                <span>发布 {video.create_time}</span>
                {video.duration > 0 && (
                  <span>时长 {Math.floor(video.duration / 60)}:{String(video.duration % 60).padStart(2, '0')}</span>
                )}
                {video.music_title && (
                  <span className="flex items-center gap-1">
                    <Music className="w-3 h-3" /> {video.music_title}
                  </span>
                )}
              </div>

              {/* 标签 */}
              {video.tags && (
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {video.tags.split(/[,，]/).filter(Boolean).map((tag, i) => (
                    <span key={i} className="px-2.5 py-1 bg-blue-50 text-blue-600 rounded-full text-xs">
                      #{tag.trim()}
                    </span>
                  ))}
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
                {video.video_url && (
                  <a
                    href={video.video_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
                  >
                    <Download className="w-4 h-4" /> 无水印下载
                  </a>
                )}
                <span className="flex items-center gap-1 text-xs text-emerald-500">
                  <CheckCircle className="w-3.5 h-3.5" /> 已同步至飞书
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
