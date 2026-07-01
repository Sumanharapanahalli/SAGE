import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CodeBlock from '../components/ui/CodeBlock'

describe('CodeBlock', () => {
  it('renders its children text inside a <pre>', () => {
    const { container } = render(<CodeBlock>{'line one\nline two'}</CodeBlock>)
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
    expect(pre).toHaveTextContent('line one')
    expect(pre).toHaveTextContent('line two')
  })

  it('overlays a copy button with an accessible name', () => {
    render(<CodeBlock>{'payload'}</CodeBlock>)
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
  })

  it('appends the className prop to the <pre>', () => {
    const { container } = render(<CodeBlock className="whitespace-pre-wrap">{'x'}</CodeBlock>)
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
    expect(pre?.className).toContain('whitespace-pre-wrap')
  })
})
