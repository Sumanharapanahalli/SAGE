import React, { forwardRef, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

// Modal — an accessible dialog primitive. Follows the ui/ convention (inline
// --sage-* tokens, forwardRef, injected style tag once). Provides: portal to
// <body>, overlay-click + Escape to close, body scroll-lock while open, focus
// moved into the dialog on open and restored on close, and a Tab focus-trap.

type ModalSize = 'sm' | 'md' | 'lg';

// Omit the native string `title` — the modal header takes a ReactNode instead.
interface ModalProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  open: boolean;
  onClose: () => void;
  size?: ModalSize;
  title?: React.ReactNode;
  closeOnOverlay?: boolean;
}

const sizeWidth: Record<ModalSize, string> = { sm: '24rem', md: '32rem', lg: '48rem' };

if (typeof document !== 'undefined') {
  const STYLE_ID = 'sage-modal-styles';
  if (!document.getElementById(STYLE_ID)) {
    const el = document.createElement('style');
    el.id = STYLE_ID;
    el.textContent = `
      @keyframes sage-modal-in {
        from { opacity: 0; transform: translateY(8px) scale(0.98); }
        to   { opacity: 1; transform: none; }
      }
      .sage-modal-close:hover { background-color: var(--sage-surface-muted); }
      .sage-modal-close:focus-visible { outline: 2px solid var(--sage-accent); outline-offset: 1px; }
    `;
    document.head.appendChild(el);
  }
}

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

const Modal = forwardRef<HTMLDivElement, ModalProps>(
  ({ open, onClose, size = 'md', title, closeOnOverlay = true, style, className, children, ...rest }, ref) => {
    const dialogRef = useRef<HTMLDivElement | null>(null);

    // merge the forwarded ref with the internal one (needed for focus handling)
    const setRefs = useCallback(
      (node: HTMLDivElement | null) => {
        dialogRef.current = node;
        if (typeof ref === 'function') ref(node);
        else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
      },
      [ref]
    );

    useEffect(() => {
      if (!open) return;
      const prevActive = document.activeElement as HTMLElement | null;
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';

      const visibleFocusable = () =>
        Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter(
          (el) => el.offsetParent !== null
        );

      // move focus into the dialog
      const first = visibleFocusable()[0];
      (first ?? dialogRef.current)?.focus();

      const onKey = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          onClose();
          return;
        }
        if (e.key === 'Tab') {
          const f = visibleFocusable();
          if (!f.length) return;
          const firstEl = f[0];
          const lastEl = f[f.length - 1];
          if (e.shiftKey && document.activeElement === firstEl) {
            e.preventDefault();
            lastEl.focus();
          } else if (!e.shiftKey && document.activeElement === lastEl) {
            e.preventDefault();
            firstEl.focus();
          }
        }
      };
      document.addEventListener('keydown', onKey);

      return () => {
        document.removeEventListener('keydown', onKey);
        document.body.style.overflow = prevOverflow;
        prevActive?.focus?.();
      };
    }, [open, onClose]);

    if (!open || typeof document === 'undefined') return null;

    const overlayStyle: React.CSSProperties = {
      position: 'fixed',
      inset: 0,
      backgroundColor: 'var(--sage-overlay)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      zIndex: 1000,
    };
    const dialogStyle: React.CSSProperties = {
      backgroundColor: 'var(--sage-surface)',
      color: 'var(--sage-text)',
      border: '1px solid var(--sage-border)',
      borderRadius: '0.625rem',
      width: '100%',
      maxWidth: sizeWidth[size],
      maxHeight: '85vh',
      overflow: 'auto',
      boxShadow: '0 10px 40px rgba(0, 0, 0, 0.18)',
      animation: 'sage-modal-in 0.15s ease-out',
      ...style,
    };

    return createPortal(
      <div
        style={overlayStyle}
        onMouseDown={(e) => {
          if (closeOnOverlay && e.target === e.currentTarget) onClose();
        }}
      >
        <div
          ref={setRefs}
          role="dialog"
          aria-modal="true"
          tabIndex={-1}
          className={className}
          style={dialogStyle}
          {...rest}
        >
          {title != null && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1rem 1.25rem',
                borderBottom: '1px solid var(--sage-border)',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{title}</div>
              <button
                type="button"
                aria-label="Close"
                onClick={onClose}
                className="sage-modal-close"
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: 'var(--sage-text-muted)',
                  borderRadius: '0.375rem',
                  padding: '0.25rem',
                  lineHeight: 0,
                }}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <div style={{ padding: '1.25rem' }}>{children}</div>
        </div>
      </div>,
      document.body
    );
  }
);

Modal.displayName = 'Modal';

export { Modal };
export type { ModalProps, ModalSize };
