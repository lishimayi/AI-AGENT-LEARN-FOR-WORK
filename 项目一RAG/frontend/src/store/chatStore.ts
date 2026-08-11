import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  sources?: Source[]
}

export interface Source {
  content: string
  metadata: {
    source?: string
    doc_type?: string
    file_name?: string
  }
  score: number
}

interface ChatState {
  messages: Message[]
  isLoading: boolean
  sessionId: string | null
  websocket: WebSocket | null
  
  // Actions
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void
  updateLastMessage: (content: string) => void
  setLoading: (loading: boolean) => void
  clearMessages: () => void
  setSessionId: (id: string) => void
  connectWebSocket: () => void
  disconnectWebSocket: () => void
  sendMessage: (content: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  sessionId: null,
  websocket: null,
  
  addMessage: (message) => {
    const newMessage: Message = {
      ...message,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now()
    }
    set((state) => ({
      messages: [...state.messages, newMessage]
    }))
  },
  
  updateLastMessage: (content) => {
    set((state) => {
      const messages = [...state.messages]
      if (messages.length > 0) {
        messages[messages.length - 1].content = content
      }
      return { messages }
    })
  },
  
  setLoading: (loading) => set({ isLoading: loading }),
  
  clearMessages: () => set({ messages: [] }),
  
  setSessionId: (id) => set({ sessionId: id }),
  
  connectWebSocket: () => {
    const state = get()
    if (state.websocket?.readyState === WebSocket.OPEN) {
      return
    }
    
    const sessionId = state.sessionId || `session_${Date.now()}`
    const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)
    
    ws.onopen = () => {
      console.log('WebSocket connected')
      set({ sessionId, websocket: ws })
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'content') {
        state.updateLastMessage((state.messages[state.messages.length - 1]?.content || '') + data.content)
      } else if (data.type === 'complete') {
        set({ isLoading: false })
      } else if (data.type === 'error') {
        state.updateLastMessage(`错误: ${data.content}`)
        set({ isLoading: false })
      }
    }
    
    ws.onclose = () => {
      console.log('WebSocket disconnected')
      set({ websocket: null })
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      set({ isLoading: false })
    }
  },
  
  disconnectWebSocket: () => {
    const { websocket } = get()
    if (websocket) {
      websocket.close()
      set({ websocket: null })
    }
  },
  
  sendMessage: (content) => {
    const { websocket, addMessage, setLoading } = get()
    
    addMessage({ role: 'user', content })
    setLoading(true)
    
    if (websocket?.readyState === WebSocket.OPEN) {
      // 添加一个空的 assistant 消息用于流式更新
      addMessage({ role: 'assistant', content: '' })
      websocket.send(JSON.stringify({ question: content }))
    } else {
      // 非 WebSocket 模式，使用 HTTP 请求
      addMessage({ role: 'assistant', content: '' })
      setLoading(true)
      
      fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: content })
      })
        .then(res => res.json())
        .then(data => {
          get().updateLastMessage(data.answer || '没有收到响应')
        })
        .catch(err => {
          get().updateLastMessage(`请求失败: ${err.message}`)
        })
        .finally(() => {
          setLoading(false)
        })
    }
  }
}))
