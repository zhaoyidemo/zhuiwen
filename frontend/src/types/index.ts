export interface VideoData {
  aweme_id: string
  account_id: string
  desc: string
  create_time: string
  duration: number
  play_count: number
  digg_count: number
  comment_count: number
  collect_count: number
  share_count: number
  collect_rate: number
  tags: string
  music_title: string
  video_url: string
  cover_url: string
  is_co_creation: boolean
  co_creation_users: string
  source_url: string
  author_nickname?: string
  author_avatar?: string
  author_unique_id?: string
  author_follower_count?: number
}

export interface AccountData {
  account_id: string
  sec_user_id: string
  unique_id: string
  nickname: string
  avatar_url: string
  follower_count: number
  following_count: number
  total_favorited: number
  video_count: number
  signature: string
  is_own_account: boolean
  category: string
  last_synced_at: string
  notes: string
}

export interface AnalysisResult {
  analysis_id: string
  analysis_type: string
  input_description: string
  result: string
  created_at: string
}

export interface SyncResult {
  message: string
  total: number
  synced_to_feishu: number
  videos: VideoData[]
}
