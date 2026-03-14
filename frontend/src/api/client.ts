import axios from 'axios'
import type { VideoData, AccountData, SyncResult, AnalysisResult } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 请求拦截器：添加密码
api.interceptors.request.use((config) => {
  const password = localStorage.getItem('site_password') || ''
  config.headers['X-Site-Password'] = password
  return config
})

// 响应拦截器：处理 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('site_password')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

export async function verifyPassword(password: string): Promise<boolean> {
  try {
    await axios.post('/api/auth/verify', { password })
    return true
  } catch {
    return false
  }
}

export async function parseVideo(url: string): Promise<VideoData> {
  const { data } = await api.post('/video/parse', { url })
  return data
}

export async function getVideo(awemeId: string): Promise<VideoData> {
  const { data } = await api.get(`/video/${awemeId}`)
  return data
}

export async function addAccount(uniqueId: string, category: string): Promise<AccountData> {
  const { data } = await api.post('/account/add', { unique_id: uniqueId, category })
  return data
}

export async function syncAccountVideos(secUserId: string): Promise<SyncResult> {
  const { data } = await api.post(`/account/${secUserId}/sync`)
  return data
}

export async function getAccounts(): Promise<{ accounts: AccountData[] }> {
  const { data } = await api.get('/account/list')
  return data
}

export async function getAccountVideos(
  accountId: string,
  sortBy = 'collect_rate',
  order = 'desc'
): Promise<{ videos: VideoData[]; total: number }> {
  const { data } = await api.get(`/account/${accountId}/videos`, {
    params: { sort_by: sortBy, order },
  })
  return data
}

export async function runAnalysis(
  videoIds: string[],
  analysisType: string,
  customPrompt?: string
): Promise<AnalysisResult> {
  const { data } = await api.post('/analysis/run', {
    video_ids: videoIds,
    analysis_type: analysisType,
    custom_prompt: customPrompt,
  })
  return data
}
