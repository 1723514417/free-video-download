<template>
  <div class="app">
    <div class="bg-effects">
      <div class="bg-orb bg-orb-1"></div>
      <div class="bg-orb bg-orb-2"></div>
      <div class="bg-orb bg-orb-3"></div>
    </div>

    <header class="header">
      <div class="logo">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
        </div>
        <span class="logo-text">VideoSaver</span>
      </div>
      <nav class="nav">
        <a href="#features" class="nav-link">功能</a>
        <a href="#platforms" class="nav-link">支持平台</a>
        <a href="#faq" class="nav-link">常见问题</a>
      </nav>
    </header>

    <main class="main">
      <section class="hero">
        <h1 class="hero-title">
          <span class="gradient-text">全网视频</span>，一键下载
        </h1>
        <p class="hero-subtitle">
          支持 YouTube、B站、抖音、TikTok、Twitter 等 1800+ 平台
          <br />高清无水印，手机电脑都能用
        </p>

        <div class="input-section">
          <div class="input-wrapper" :class="{ focused: isInputFocused, 'has-error': error }">
            <div class="input-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            </div>
            <input
              v-model="videoUrl"
              type="text"
              placeholder="粘贴视频链接到这里... 如 https://www.youtube.com/watch?v=..."
              class="url-input"
              @focus="isInputFocused = true"
              @blur="isInputFocused = false"
              @keydown.enter="parseVideo"
              :disabled="isLoading"
            />
            <button class="parse-btn" @click="parseVideo" :disabled="isLoading || !videoUrl.trim()">
              <span v-if="isLoading" class="spinner"></span>
              <span v-else class="btn-content">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                解析
              </span>
            </button>
          </div>
          <p v-if="error" class="error-msg">{{ error }}</p>
        </div>
      </section>

      <transition name="fade-up">
        <section v-if="videoInfo" class="result-section">
          <div class="result-card">
            <div class="result-header">
              <div class="thumbnail-wrapper">
                <img
                  v-if="videoInfo.thumbnail"
                  :src="`/api/proxy-image?url=${encodeURIComponent(videoInfo.thumbnail)}`"
                  :alt="videoInfo.title"
                  class="thumbnail"
                  @error="handleThumbnailError"
                />
                <div v-else class="thumbnail-placeholder">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="2" y="2" width="20" height="20" rx="2" />
                    <polygon points="10 8 16 12 10 16 10 8" />
                  </svg>
                </div>
                <span v-if="videoInfo.duration" class="duration-badge">
                  {{ formatDuration(videoInfo.duration) }}
                </span>
              </div>
              <div class="result-info">
                <h2 class="video-title">{{ videoInfo.title }}</h2>
                <p v-if="videoInfo.uploader" class="video-uploader">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  {{ videoInfo.uploader }}
                </p>
                <p v-if="videoInfo.description" class="video-desc">{{ videoInfo.description }}</p>
              </div>
            </div>

            <div class="formats-section">
              <h3 class="formats-title">选择画质 / 格式</h3>
              <div class="formats-grid">
                <button
                  v-for="fmt in videoInfo.formats"
                  :key="fmt.format_id"
                  class="format-btn"
                  :class="{ active: selectedFormat === fmt.format_id, audio: fmt.resolution === '音频' }"
                  @click="selectedFormat = fmt.format_id"
                >
                  <div class="format-main">
                    <span class="format-resolution">{{ fmt.resolution }}</span>
                    <span class="format-ext">.{{ fmt.ext }}</span>
                  </div>
                  <div class="format-meta">
                    <span v-if="fmt.filesize || fmt.filesize_approx" class="format-size">
                      {{ formatFileSize(fmt.filesize || fmt.filesize_approx) }}
                    </span>
                    <span v-if="fmt.tbr" class="format-bitrate">{{ Math.round(fmt.tbr) }}kbps</span>
                  </div>
                </button>
              </div>
            </div>

            <div class="download-actions">
              <button
                class="download-btn"
                @click="downloadVideo"
                :disabled="isDownloading || !selectedFormat"
              >
                <span v-if="isDownloading" class="spinner"></span>
                <template v-else>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  立即下载
                </template>
                <span v-if="isDownloading" class="download-status">{{ downloadStatus }}</span>
              </button>
            </div>
          </div>
        </section>
      </transition>

      <section id="features" class="features-section">
        <h2 class="section-title">为什么选择 VideoSaver？</h2>
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon feature-icon-1">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <h3>极速下载</h3>
            <p>多线程加速，下载速度拉满，大文件也不在话下</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon feature-icon-2">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
            </div>
            <h3>全平台支持</h3>
            <p>1800+ 视频平台，国内外主流站点全覆盖</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon feature-icon-3">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h3>高清无水印</h3>
            <p>支持 4K/2K/1080P，原始画质，无任何水印</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon feature-icon-4">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="5" y="2" width="14" height="20" rx="2" />
                <line x1="12" y1="18" x2="12.01" y2="18" />
              </svg>
            </div>
            <h3>手机也能用</h3>
            <p>响应式设计，手机浏览器直接打开就能下载</p>
          </div>
        </div>
      </section>

      <section id="platforms" class="platforms-section">
        <h2 class="section-title">支持各大平台</h2>
        <p class="section-desc">持续更新，覆盖全球主流视频站点</p>
        <div class="platforms-grid">
          <div v-for="category in platformCategories" :key="category.name" class="platform-group">
            <h3 class="platform-group-title">{{ category.name }}</h3>
            <div class="platform-tags">
              <span v-for="site in category.sites" :key="site.name" class="platform-tag">
                {{ site.name }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section id="faq" class="faq-section">
        <h2 class="section-title">常见问题</h2>
        <div class="faq-list">
          <div
            v-for="(item, idx) in faqItems"
            :key="idx"
            class="faq-item"
            :class="{ open: openFaq === idx }"
            @click="openFaq = openFaq === idx ? -1 : idx"
          >
            <div class="faq-question">
              <span>{{ item.q }}</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="faq-arrow">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>
            <transition name="expand">
              <div v-if="openFaq === idx" class="faq-answer">{{ item.a }}</div>
            </transition>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <p>VideoSaver — 站在巨人的肩膀上，基于 <a href="https://github.com/yt-dlp/yt-dlp" target="_blank">yt-dlp</a> 开源项目</p>
      <p class="footer-note">仅供学习交流使用，请遵守当地法律法规</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const videoUrl = ref('')
const isLoading = ref(false)
const isDownloading = ref(false)
const isInputFocused = ref(false)
const error = ref('')
const videoInfo = ref(null)
const selectedFormat = ref('')
const platformCategories = ref([])
const openFaq = ref(-1)
const downloadStatus = ref('')

const faqItems = [
  { q: '支持哪些视频平台？', a: '支持 YouTube、Bilibili（B站）、抖音、TikTok、Twitter/X、Instagram、Facebook、快手、微博、小红书、优酷、爱奇艺、腾讯视频等 1800+ 全球主流视频平台。' },
  { q: '下载的视频有水印吗？', a: '我们尽量获取原始高清视频源，大多数平台支持无水印下载。部分平台（如抖音）可自动去除水印。' },
  { q: '手机上能用吗？', a: '完全可以！VideoSaver 采用响应式设计，在手机浏览器中打开即可使用，无需安装任何 App。' },
  { q: '支持什么画质？', a: '根据视频源不同，最高支持 4K (2160P) 画质。也支持 2K、1080P、720P、480P 等多种清晰度选择。' },
  { q: '可以下载音频吗？', a: '可以！支持提取纯音频（MP3/M4A 格式），适合下载音乐、播客等内容。' },
  { q: '收费吗？', a: '基础功能完全免费。如需批量下载、更高速度等高级功能，请关注我们的会员计划。' },
]

onMounted(async () => {
  try {
    const res = await fetch('/api/supported-sites')
    const data = await res.json()
    platformCategories.value = data.categories || []
  } catch {
    platformCategories.value = []
  }
})

async function parseVideo() {
  if (!videoUrl.value.trim()) return
  error.value = ''
  videoInfo.value = null
  selectedFormat.value = ''
  isLoading.value = true

  try {
    const res = await fetch('/api/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: videoUrl.value.trim() }),
    })
    const data = await res.json()
    if (!res.ok) {
      error.value = data.detail || '解析失败，请检查链接是否正确'
      return
    }
    videoInfo.value = data
    if (data.formats && data.formats.length > 0) {
      selectedFormat.value = data.formats[0].format_id
    }
  } catch (e) {
    error.value = '网络错误，请检查后端服务是否启动'
  } finally {
    isLoading.value = false
  }
}

async function downloadVideo() {
  if (!selectedFormat.value || !videoInfo.value) return
  isDownloading.value = true
  downloadStatus.value = '准备下载中...'

  try {
    const downloadUrl = `/api/download?url=${encodeURIComponent(videoInfo.value.webpage_url || videoUrl.value)}&format_id=${selectedFormat.value}`

    downloadStatus.value = '服务器正在获取视频...'

    const response = await fetch(downloadUrl)
    if (!response.ok) {
      const errData = await response.json().catch(() => null)
      throw new Error(errData?.detail || '下载失败')
    }

    const contentLength = response.headers.get('content-length')
    const total = contentLength ? parseInt(contentLength) : 0
    const reader = response.body.getReader()

    let received = 0
    const chunks = []
    let lastStatusUpdate = 0

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(value)
      received += value.length

      const now = Date.now()
      if (now - lastStatusUpdate > 300) {
        lastStatusUpdate = now
        if (total > 0) {
          const pct = Math.round((received / total) * 100)
          downloadStatus.value = `下载中 ${pct}% (${formatFileSize(received)} / ${formatFileSize(total)})`
        } else {
          downloadStatus.value = `下载中... ${formatFileSize(received)}`
        }
      }
    }

    downloadStatus.value = '正在保存...'

    const blob = new Blob(chunks)
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    const ext = videoInfo.value.formats.find(f => f.format_id === selectedFormat.value)?.ext || 'mp4'
    const safeName = (videoInfo.value.title || 'video').replace(/[\\/:*?"<>|]/g, '_')
    a.download = `${safeName}.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)

    downloadStatus.value = '下载完成!'
  } catch (e) {
    error.value = e.message || '下载失败，请重试'
  } finally {
    setTimeout(() => {
      isDownloading.value = false
      downloadStatus.value = ''
    }, 1500)
  }
}

function formatDuration(seconds) {
  if (!seconds) return ''
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB'
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

function handleThumbnailError(e) {
  e.target.style.display = 'none'
}
</script>

<style>
:root {
  --bg-primary: #07070d;
  --bg-secondary: #0f0f1a;
  --bg-card: rgba(15, 15, 30, 0.8);
  --bg-card-hover: rgba(25, 25, 50, 0.9);
  --border-color: rgba(99, 102, 241, 0.15);
  --border-active: rgba(99, 102, 241, 0.5);
  --text-primary: #f0f0ff;
  --text-secondary: #8888aa;
  --text-muted: #555577;
  --accent-1: #6366f1;
  --accent-2: #8b5cf6;
  --accent-3: #a78bfa;
  --success: #10b981;
  --error: #ef4444;
  --gradient: linear-gradient(135deg, #6366f1, #8b5cf6, #a78bfa);
  --gradient-subtle: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1));
  --radius: 16px;
  --radius-sm: 10px;
  --radius-xs: 6px;
  --shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 48px rgba(99, 102, 241, 0.15);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}

.app {
  min-height: 100vh;
  position: relative;
}

.bg-effects {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.4;
  animation: float 20s ease-in-out infinite;
}

.bg-orb-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(99,102,241,0.3), transparent 70%);
  top: -200px;
  left: -100px;
  animation-delay: 0s;
}

.bg-orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(139,92,246,0.25), transparent 70%);
  top: 40%;
  right: -150px;
  animation-delay: -7s;
}

.bg-orb-3 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(167,139,250,0.2), transparent 70%);
  bottom: -100px;
  left: 30%;
  animation-delay: -14s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(30px, -40px) scale(1.05); }
  50% { transform: translate(-20px, 20px) scale(0.95); }
  75% { transform: translate(40px, 30px) scale(1.02); }
}

.header {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 40px;
  backdrop-filter: blur(20px);
  background: rgba(7, 7, 13, 0.6);
  border-bottom: 1px solid var(--border-color);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: var(--gradient);
  border-radius: var(--radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  color: white;
}

.logo-icon svg {
  width: 100%;
  height: 100%;
}

.logo-text {
  font-size: 22px;
  font-weight: 800;
  background: var(--gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}

.nav {
  display: flex;
  gap: 32px;
}

.nav-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.3s;
}

.nav-link:hover {
  color: var(--text-primary);
}

.main {
  position: relative;
  z-index: 5;
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
}

.hero {
  text-align: center;
  padding: 80px 0 60px;
}

.hero-title {
  font-size: clamp(36px, 6vw, 64px);
  font-weight: 900;
  line-height: 1.1;
  letter-spacing: -2px;
  margin-bottom: 20px;
}

.gradient-text {
  background: var(--gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-subtitle {
  font-size: 18px;
  color: var(--text-secondary);
  line-height: 1.8;
  margin-bottom: 48px;
  font-weight: 400;
}

.input-section {
  max-width: 720px;
  margin: 0 auto;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 0;
  background: var(--bg-card);
  border: 1.5px solid var(--border-color);
  border-radius: var(--radius);
  padding: 6px;
  transition: all 0.3s ease;
  backdrop-filter: blur(20px);
  box-shadow: var(--shadow);
}

.input-wrapper.focused {
  border-color: var(--border-active);
  box-shadow: var(--shadow-lg), 0 0 0 4px rgba(99,102,241,0.1);
}

.input-wrapper.has-error {
  border-color: var(--error);
}

.input-icon {
  padding: 0 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
}

.input-icon svg {
  width: 20px;
  height: 20px;
}

.url-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 15px;
  color: var(--text-primary);
  padding: 14px 0;
  font-family: inherit;
  min-width: 0;
}

.url-input::placeholder {
  color: var(--text-muted);
}

.url-input:disabled {
  opacity: 0.6;
}

.parse-btn {
  background: var(--gradient);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  font-size: 15px;
  font-weight: 600;
  padding: 14px 28px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
  white-space: nowrap;
  font-family: inherit;
}

.parse-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4);
}

.parse-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-content svg {
  width: 18px;
  height: 18px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2.5px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-msg {
  color: var(--error);
  font-size: 13px;
  margin-top: 12px;
  text-align: left;
  padding-left: 4px;
}

.fade-up-enter-active {
  animation: fadeUp 0.5s ease-out;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.result-section {
  margin-bottom: 80px;
}

.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 28px;
  backdrop-filter: blur(20px);
  box-shadow: var(--shadow);
}

.result-header {
  display: flex;
  gap: 24px;
  margin-bottom: 28px;
}

.thumbnail-wrapper {
  position: relative;
  width: 240px;
  min-width: 240px;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.thumbnail-placeholder svg {
  width: 48px;
  height: 48px;
}

.duration-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.result-info {
  flex: 1;
  min-width: 0;
}

.video-title {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.video-uploader {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 8px;
}

.video-desc {
  color: var(--text-muted);
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.formats-section {
  margin-bottom: 24px;
}

.formats-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 14px;
}

.formats-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.format-btn {
  background: var(--bg-secondary);
  border: 1.5px solid var(--border-color);
  border-radius: var(--radius-xs);
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.25s;
  color: var(--text-primary);
  text-align: left;
  font-family: inherit;
}

.format-btn:hover {
  border-color: var(--border-active);
  background: var(--bg-card-hover);
}

.format-btn.active {
  border-color: var(--accent-1);
  background: rgba(99, 102, 241, 0.15);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.format-btn.audio {
  border-color: rgba(16, 185, 129, 0.2);
}

.format-btn.audio.active {
  border-color: var(--success);
  background: rgba(16, 185, 129, 0.1);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
}

.format-main {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 4px;
}

.format-resolution {
  font-weight: 700;
  font-size: 15px;
}

.format-ext {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.format-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: var(--text-muted);
}

.format-size {
  color: var(--accent-3);
  font-weight: 500;
}

.download-actions {
  display: flex;
  gap: 12px;
}

.download-btn {
  background: linear-gradient(135deg, var(--success), #059669);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  font-size: 16px;
  font-weight: 700;
  padding: 16px 40px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.3s;
  font-family: inherit;
}

.download-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(16, 185, 129, 0.4);
}

.download-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.download-btn svg {
  width: 20px;
  height: 20px;
}

.download-status {
  font-size: 13px;
  font-weight: 500;
  opacity: 0.9;
  white-space: nowrap;
}

.features-section,
.platforms-section,
.faq-section {
  padding: 80px 0;
}

.section-title {
  font-size: 32px;
  font-weight: 800;
  text-align: center;
  margin-bottom: 12px;
  letter-spacing: -1px;
}

.section-desc {
  text-align: center;
  color: var(--text-secondary);
  margin-bottom: 48px;
  font-size: 16px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.feature-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 32px 24px;
  text-align: center;
  backdrop-filter: blur(20px);
  transition: all 0.3s;
}

.feature-card:hover {
  transform: translateY(-4px);
  border-color: var(--border-active);
  box-shadow: var(--shadow-lg);
}

.feature-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.feature-icon svg {
  width: 28px;
  height: 28px;
}

.feature-icon-1 {
  background: rgba(99, 102, 241, 0.15);
  color: var(--accent-1);
}
.feature-icon-2 {
  background: rgba(139, 92, 246, 0.15);
  color: var(--accent-2);
}
.feature-icon-3 {
  background: rgba(16, 185, 129, 0.15);
  color: var(--success);
}
.feature-icon-4 {
  background: rgba(244, 114, 182, 0.15);
  color: #f472b6;
}

.feature-card h3 {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 10px;
}

.feature-card p {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.platforms-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 28px;
}

.platform-group {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 28px;
  backdrop-filter: blur(20px);
}

.platform-group-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 16px;
  color: var(--accent-3);
}

.platform-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.platform-tag {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.platform-tag:hover {
  border-color: var(--border-active);
  color: var(--text-primary);
  background: rgba(99, 102, 241, 0.1);
}

.faq-list {
  max-width: 720px;
  margin: 0 auto;
}

.faq-item {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.3s;
  backdrop-filter: blur(20px);
}

.faq-item:hover,
.faq-item.open {
  border-color: var(--border-active);
}

.faq-question {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  font-weight: 600;
  font-size: 15px;
}

.faq-arrow {
  width: 18px;
  height: 18px;
  transition: transform 0.3s;
  flex-shrink: 0;
  color: var(--text-muted);
}

.faq-item.open .faq-arrow {
  transform: rotate(180deg);
}

.faq-answer {
  padding: 0 24px 20px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.expand-enter-active {
  animation: expandIn 0.3s ease-out;
}

@keyframes expandIn {
  from {
    opacity: 0;
    max-height: 0;
  }
  to {
    opacity: 1;
    max-height: 200px;
  }
}

.footer {
  position: relative;
  z-index: 5;
  text-align: center;
  padding: 40px 24px;
  border-top: 1px solid var(--border-color);
  color: var(--text-muted);
  font-size: 13px;
}

.footer a {
  color: var(--accent-3);
  text-decoration: none;
}

.footer a:hover {
  text-decoration: underline;
}

.footer-note {
  margin-top: 6px;
  font-size: 12px;
  opacity: 0.6;
}

@media (max-width: 768px) {
  .header {
    padding: 16px 20px;
  }

  .nav {
    display: none;
  }

  .hero {
    padding: 48px 0 40px;
  }

  .hero-subtitle {
    font-size: 15px;
    margin-bottom: 32px;
  }

  .hero-subtitle br {
    display: none;
  }

  .input-wrapper {
    flex-direction: column;
    padding: 12px;
    gap: 10px;
  }

  .input-icon {
    display: none;
  }

  .url-input {
    width: 100%;
    padding: 10px 0;
    text-align: center;
  }

  .parse-btn {
    width: 100%;
    justify-content: center;
    padding: 14px;
  }

  .result-header {
    flex-direction: column;
  }

  .thumbnail-wrapper {
    width: 100%;
    min-width: 100%;
  }

  .features-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .feature-card {
    padding: 24px 16px;
  }

  .platforms-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .section-title {
    font-size: 26px;
  }

  .result-card {
    padding: 20px;
  }

  .formats-grid {
    gap: 8px;
  }

  .format-btn {
    padding: 8px 12px;
  }

  .download-btn {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .features-grid {
    grid-template-columns: 1fr;
  }
}
</style>
