import { useState, useEffect } from 'react'

interface OtherSelectProps {
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  className?: string
  style?: React.CSSProperties
  inputStyle?: React.CSSProperties
  otherLabel?: string
}

/**
 * A select element with an "Other..." option at the bottom.
 * When "Other..." is selected, a text input appears for custom freetext.
 */
export default function OtherSelect({
  value,
  onChange,
  options,
  placeholder,
  className,
  style,
  inputStyle,
  otherLabel = 'Other...',
}: OtherSelectProps) {
  const knownValues = options.map(o => o.value)
  const isOther = value !== '' && !knownValues.includes(value)

  const [showInput, setShowInput] = useState(isOther)
  const [inputVal, setInputVal] = useState(isOther ? value : '')

  useEffect(() => {
    const nowOther = value !== '' && !knownValues.includes(value)
    setShowInput(nowOther)
    if (nowOther) setInputVal(value)
  }, [value])

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (e.target.value === '__other__') {
      setShowInput(true)
      setInputVal('')
      onChange('')
    } else {
      setShowInput(false)
      setInputVal('')
      onChange(e.target.value)
    }
  }

  const selectValue = isOther || showInput ? '__other__' : value

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <select
        value={selectValue}
        onChange={handleSelectChange}
        className={className}
        style={style}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
        <option value="__other__">{otherLabel}</option>
      </select>

      {showInput && (
        <input
          type="text"
          value={inputVal}
          onChange={e => { setInputVal(e.target.value); onChange(e.target.value) }}
          placeholder="Type custom value..."
          autoFocus
          style={{
            border: '1px solid #d1d5db',
            padding: '6px 10px',
            fontSize: '13px',
            width: '100%',
            boxSizing: 'border-box',
            ...inputStyle,
          }}
        />
      )}
    </div>
  )
}
