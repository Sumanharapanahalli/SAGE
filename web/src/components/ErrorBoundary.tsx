import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100vh', background: '#0a0a0c', color: '#e4e4e7', fontFamily: 'system-ui, sans-serif',
        }}>
          <h1 style={{ fontSize: 18, marginBottom: 8 }}>Something went wrong</h1>
          <p style={{ fontSize: 13, color: '#9ca3af', marginBottom: 16, maxWidth: 400, textAlign: 'center' }}>
            {this.state.error?.message ?? 'An unexpected error occurred.'}
          </p>
          <button
            onClick={this.handleRetry}
            aria-label="Retry"
            style={{
              padding: '8px 20px', fontSize: 13, borderRadius: 6,
              background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
