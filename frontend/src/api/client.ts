import axios from 'axios'

function getBaseURL(): string {
  const configured = window.__APP_CONFIG__?.apiBaseUrl
  if (configured) {
    return configured.replace(/\/$/, '') + '/api/v1'
  }
  return '/api/v1'
}

const client = axios.create({
  baseURL: getBaseURL(),
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.error || error.message || '网络错误'
    console.error('API Error:', msg)
    return Promise.reject(new Error(msg))
  }
)

export default client
