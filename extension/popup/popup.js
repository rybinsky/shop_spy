async function checkBackend() {
  const statusEl = document.getElementById('status');
  try {
    const resp = await fetch('https://shop-spy.onrender.com/api/stats');
    const data = await resp.json();
    statusEl.className = 'status ok';
    statusEl.innerHTML = '<span class="status-dot"></span> Сервер работает';
    document.getElementById('stat-products').textContent = data.unique_products || 0;
    document.getElementById('stat-records').textContent = data.total_records || 0;
  } catch (e) {
    statusEl.className = 'status error';
    statusEl.innerHTML = '<span class="status-dot"></span> Сервер просыпается... подождите 30 сек';
  }
}
checkBackend();
