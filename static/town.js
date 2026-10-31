'use strict';
const output = document.getElementById('activity-output');
if (output) {
  let revision = null;
  let rendered = '';
  let readingVersion = '';
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
      const readings = data.readings || [];
      const nextReadingVersion = JSON.stringify(readings);
      const readingOutput = document.getElementById('reading-results');
      if (readingOutput && readingVersion !== nextReadingVersion) {
        readingOutput.replaceChildren();
        for (const item of [...readings].reverse()) {
          const article = document.createElement('article');
          article.className = 'memory';
          const title = document.createElement('a');
          title.href = '/thread/' + encodeURIComponent(item.id);
          title.textContent = item.title;
          const body = document.createElement('p');
          body.textContent = item.body;
          article.append(title, body);
          if (item.url.startsWith('https://')) {
            const source = document.createElement('a');
            source.href = item.url;
            source.target = '_blank';
            source.rel = 'noopener noreferrer';
            source.textContent = 'Read original source ↗';
            article.append(source);
          }
          readingOutput.append(article);
        }
        if (!readings.length) readingOutput.textContent = 'No successful outside readings yet. Send a resident reading above; check Live activity if nothing appears.';
        readingVersion = nextReadingVersion;
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
