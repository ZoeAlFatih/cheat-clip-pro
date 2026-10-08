import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { useLanguage } from '../locales';
import { resilientFetch } from '../utils/api';

type GateState = 'checking' | 'locked' | 'open';

/**
 * Asks for the server access key (CHEAT_CLIP_API_KEY) when the backend requires one.
 * The key is exchanged for an HttpOnly session cookie, so every later request
 * (fetch, <video>, <img>, downloads, EventSource) is authorized without extra code.
 */
export default function AccessKeyGate({ children }: { children: ReactNode }) {
  const { t } = useLanguage();
  const [state, setState] = useState<GateState>('checking');
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    resilientFetch('/api/auth/status', { maxRetries: 6, retryDelay: 800, silent: true })
      .then((res) => res.json())
      .then((data) => setState(data.required && !data.authenticated ? 'locked' : 'open'))
      // Backend unreachable: let the app load and show its own connection errors.
      .catch(() => setState('open'));
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const res = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: key.trim() }),
      });
      if (res.ok) {
        setState('open');
      } else {
        setError(t.auth.invalid);
      }
    } catch {
      setError(t.auth.unreachable);
    } finally {
      setSubmitting(false);
    }
  };

  if (state === 'open') return <>{children}</>;
  if (state === 'checking') return null;

  return (
    <div className="modal-backdrop">
      <form className="cookies-modal-card" onSubmit={submit} style={{ maxWidth: '440px' }}>
        <div className="studio-modal-header">
          <div className="studio-header-title">
            <div className="studio-icon-badge">🔐</div>
            <div>
              <div className="studio-title-row">
                <h2>{t.auth.title}</h2>
              </div>
              <p className="studio-header-desc">{t.auth.desc}</p>
            </div>
          </div>
        </div>
        <div className="cookies-modal-scrollable" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <input
            type="password"
            className="form-input"
            placeholder={t.auth.placeholder}
            value={key}
            onChange={(e) => setKey(e.target.value)}
            autoFocus
            autoComplete="current-password"
            aria-label={t.auth.placeholder}
            style={{ height: '42px' }}
          />
          {error && (
            <span role="alert" style={{ fontSize: '0.8rem', color: '#f87171' }}>
              {error}
            </span>
          )}
          <button type="submit" className="studio-btn-render glowing-btn" disabled={submitting || !key.trim()}>
            {submitting ? t.auth.checking : t.auth.submit}
          </button>
        </div>
      </form>
    </div>
  );
}
