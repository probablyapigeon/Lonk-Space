'use strict';
const output = document.getElementById('activity-output');
if (output) {
  let revision = null;
  let rendered = '';
  async function poll() {
    const status = document.getElementById('live-status');
    try {
      const response = await fetch('/activity', {cache: 'no-store'});
      if (!response.ok) throw new Error('Session or server unavailable');
      const data = await response.json();
      document.getElementById('world-tick').textContent = data.tick;
      document.getElementById('pending-status').textContent = `${data.pending} queued / running`;
      const recent = data.last_tick && Date.now()/1000-data.last_tick < 180;
      status.textContent = data.settings.paused ? 'Clock paused. Chat and queued reading still work.' : recent ? 'Connected · world clock running' : 'Connected · waiting for the world clock';
      const text = data.logs.map(item => item.text).join('\n');
      if (text !== rendered) {
        const atBottom = output.scrollHeight-output.scrollTop-output.clientHeight < 80;
        output.textContent = text || 'No activity yet. Send a resident reading or start a conversation.';
        if (atBottom || !rendered) output.scrollTop = output.scrollHeight;
        rendered = text;
      }
      if (revision !== null && revision !== data.revision) document.getElementById('fresh-notice').hidden = false;
      revision = data.revision;
    } catch (_) {
      status.textContent = 'Connection interrupted. Keep the launcher open; sign in again if your session expired.';
    }
    setTimeout(poll, 3000);
  }
  poll();
}
