const { useState, useEffect } = React;

const STATE_PALETTE = {
  available:   { bg: '#e6f9f0', color: '#1a7a4a', border: '#b7ebd2' },
  unavailable: { bg: '#fdecea', color: '#c0392b', border: '#f5b7b1' },
  busy:        { bg: '#fff4e5', color: '#b45309', border: '#fddba0' },
  'wrap-up':   { bg: '#e8f0fe', color: '#1a56db', border: '#bfcffe' },
};
const DEFAULT_PALETTE = { bg: '#f0f0f0', color: '#555', border: '#d0d0d0' };

function StateBadge({ state }) {
  const key = (state || '').toLowerCase().replace(/[_\s]/g, '-');
  const p = STATE_PALETTE[key] || DEFAULT_PALETTE;
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600,
      background: p.bg, color: p.color, border: `1px solid ${p.border}`,
      whiteSpace: 'nowrap',
    }}>
      {state || '—'}
    </span>
  );
}

function formatTs(ms) {
  if (!ms) return '—';
  return new Date(Number(ms)).toLocaleString();
}

function AgentMonitorPage() {
  const [events,   setEvents]   = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo,   setDateTo]   = useState('');
  const [userId,   setUserId]   = useState('');

  async function fetchEvents(df, dt, uid) {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (df)  params.append('date_from', new Date(df).getTime());
    if (dt)  params.append('date_to',   new Date(dt).getTime());
    if (uid) params.append('user_id', uid.trim());

    try {
      const res = await fetch(`/api/agent-events?${params}`, { credentials: 'include' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.message || `${res.status} ${res.statusText}`);
      }
      const data = await res.json();
      setEvents(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchEvents('', '', ''); }, []);

  function handleApply() { fetchEvents(dateFrom, dateTo, userId); }

  function handleClear() {
    setDateFrom('');
    setDateTo('');
    setUserId('');
    fetchEvents('', '', '');
  }

  const inputStyle = {
    padding: '7px 10px', borderRadius: 4, border: '1px solid #d0d7de',
    fontSize: 13, color: 'var(--wx-ink-700)', background: '#fff',
  };
  const labelStyle = {
    display: 'block', fontSize: 12, fontWeight: 600,
    marginBottom: 4, color: 'var(--wx-muted)',
  };

  return (
    <div>
      {/* Filter panel */}
      <div style={{
        background: 'var(--wx-surface)', borderRadius: 'var(--wx-radius)',
        padding: '16px 20px', boxShadow: '0 1px 3px rgba(16,24,40,0.06)',
        display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-end',
        marginBottom: 20,
      }}>
        <div>
          <label style={labelStyle}>Date From</label>
          <input type="datetime-local" value={dateFrom}
            onChange={e => setDateFrom(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Date To</label>
          <input type="datetime-local" value={dateTo}
            onChange={e => setDateTo(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>User ID</label>
          <input type="text" value={userId} placeholder="e.g. ce408669-9ce6-..."
            onChange={e => setUserId(e.target.value)}
            style={{ ...inputStyle, width: 280 }} />
        </div>
        <button className="btn-primary"   onClick={handleApply} style={{ height: 35 }}>Apply Filters</button>
        <button className="btn-secondary" onClick={handleClear} style={{ height: 35 }}>Clear</button>
        <button className="btn-secondary" onClick={handleApply} style={{ height: 35 }}>&#8635; Refresh</button>
      </div>

      {/* Status bar */}
      <div style={{ marginBottom: 10, fontSize: 13, color: 'var(--wx-muted)', minHeight: 20 }}>
        {loading && 'Loading...'}
        {!loading && error && <span style={{ color: '#c0392b' }}>Error: {error}</span>}
        {!loading && !error && `${events.length} record(s) found`}
      </div>

      {/* Results table */}
      <div className="table-wrapper">
        <table className="xsi-table">
          <thead>
            <tr>
              <th>#</th>
              <th>State</th>
              <th>Name</th>
              <th>Extension</th>
              <th>User ID</th>
              <th>Target ID</th>
              <th>State Time</th>
              <th>Sign-In Time</th>
              <th>Available (s)</th>
              <th>Avg Wrap-Up (s)</th>
              <th>Seq</th>
            </tr>
          </thead>
          <tbody>
            {!loading && events.length === 0 ? (
              <tr>
                <td colSpan={11} style={{ textAlign: 'center', color: 'var(--wx-muted)', padding: 24 }}>
                  No events found
                </td>
              </tr>
            ) : events.map(ev => (
              <tr key={ev.id}>
                <td style={{ color: 'var(--wx-muted)', fontSize: 12 }}>{ev.id}</td>
                <td><StateBadge state={ev.state} /></td>
                <td>{ev.name || '—'}</td>
                <td>{ev.extension || '—'}</td>
                <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{ev.user_id}</td>
                <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{ev.target_id || '—'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>{formatTs(ev.state_timestamp)}</td>
                <td style={{ whiteSpace: 'nowrap' }}>{formatTs(ev.sign_in_timestamp)}</td>
                <td>{ev.total_available_time ?? '—'}</td>
                <td>{ev.average_wrap_up_time ?? '—'}</td>
                <td>{ev.sequence_number}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<AgentMonitorPage />);
