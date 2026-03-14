import { Play, Heart, MessageCircle, Bookmark, Share2, Download, Users } from 'lucide-react'
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

function rateColor(rate: number): string {
  if (rate >= 0.05) return 'text-red-500 font-bold'
  if (rate >= 0.03) return 'text-amber-500 font-semibold'
  return 'text-emerald-500'
}

function isHotVideo(rate: number): boolean {
  return rate >= 0.03
}

interface Props {
  video: VideoData
  compact?: boolean
}

export default function VideoCard({ video, compact }: Props) {
  const stats = [
    { icon: Play, value: video.play_count, label: '播放' },
    { icon: Heart, value: video.digg_count, label: '点赞' },
    { icon: MessageCircle, value: video.comment_count, label: '评论' },
    { icon: Bookmark, value: video.collect_count, label: '收藏' },
    { icon: Share2, value: video.share_count, label: '转发' },
  ]

  return (
    <div
      className={`bg-white rounded-xl border ${
        isHotVideo(video.collect_rate) ? 'border-amber-300 ring-2 ring-amber-100' : 'border-gray-200'
      } overflow-hidden hover:shadow-md transition-shadow`}
    >
      <div className={`flex ${compact ? 'flex-row' : 'flex-col sm:flex-row'}`}>
        {/* 封面 */}
        {video.cover_url && (
          <div className={`${compact ? 'w-32 h-24' : 'w-full sm:w-48 h-36 sm:h-auto'} shrink-0 bg-gray-100`}>
            <img
              src={video.cover_url}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        )}

        {/* 信息区 */}
        <div className="flex-1 p-4 min-w-0">
          {/* 描述 */}
          <p className={`text-gray-800 text-sm ${compact ? 'line-clamp-2' : 'line-clamp-3'} mb-2`}>
            {video.desc || '(无描述)'}
          </p>

          {/* 元信息 */}
          <div className="flex items-center gap-3 text-xs text-gray-400 mb-3">
            <span>{video.create_time}</span>
            {video.duration > 0 && <span>{Math.floor(video.duration / 60)}:{String(video.duration % 60).padStart(2, '0')}</span>}
            {video.is_co_creation && (
              <span className="inline-flex items-center gap-1 text-purple-500">
                <Users className="w-3 h-3" /> 共创
              </span>
            )}
          </div>

          {/* 互动数据 */}
          <div className="flex flex-wrap gap-3 text-xs mb-3">
            {stats.map(({ icon: Icon, value, label }) => (
              <div key={label} className="flex items-center gap-1 text-gray-500">
                <Icon className="w-3.5 h-3.5" />
                <span className="tabular-nums">{formatNum(value)}</span>
              </div>
            ))}
          </div>

          {/* 收藏率 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">收藏率</span>
              <span className={`text-sm tabular-nums ${rateColor(video.collect_rate)}`}>
                {formatRate(video.collect_rate)}
              </span>
            </div>
            {video.video_url && (
              <a
                href={video.video_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-600"
              >
                <Download className="w-3.5 h-3.5" /> 下载
              </a>
            )}
          </div>

          {/* 标签 */}
          {video.tags && (
            <div className="flex flex-wrap gap-1 mt-2">
              {video.tags.split(/[,，]/).filter(Boolean).map((tag, i) => (
                <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-[11px]">
                  #{tag.trim()}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
