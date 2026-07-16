// Moor Water PWA Sync Application Logic

const DB_NAME = 'MoorWaterSyncDB';
const DB_VERSION = 1;
const STORE_NAME = 'pending_entries';
let db;

// IS_GUEST is injected by the Jinja template before this script loads
// Default to false if not set (normal logged-in mode)
// if (typeof IS_GUEST === 'undefined') { var IS_GUEST = false; }

// Form Elements
const elDate          = document.getElementById('ledgerDate');
const elFactoryStatus = document.getElementById('factoryStatus');
const elProduced      = document.getElementById('produced');
const elStorage       = document.getElementById('storage');
const elTruckSent     = document.getElementById('truckSent');
const elTruckSold     = document.getElementById('truckSold');
const elLeakages      = document.getElementById('leakages');
const elAboboyaSold   = document.getElementById('aboboyaSold');
const elFactorySold   = document.getElementById('factorySold');
const elPricePerBag   = document.getElementById('pricePerBag');
const elFuelExpenses  = document.getElementById('fuelExpenses');
const elOtherExpenses = document.getElementById('otherExpenses');
const elWithdrawBank  = document.getElementById('withdrawBank');
const elCashHand      = document.getElementById('cashHand');
const elCashBank      = document.getElementById('cashBank');
const elComments      = document.getElementById('comments');
const elForm          = document.getElementById('ledgerForm');

// Dashboard Elements
const elDashBagsSold    = document.getElementById('dashBagsSold');
const elDashRevenue     = document.getElementById('dashRevenue');
const elDashExpenses    = document.getElementById('dashExpenses');
const elDashNetCash     = document.getElementById('dashNetCash');
const elStatusDot       = document.getElementById('statusDot');
const elStatusText      = document.getElementById('statusText');
const elPendingSyncCount = document.getElementById('pendingSyncCount');

// Toast
const elToast    = document.getElementById('toast');
const elToastMsg = document.getElementById('toastMsg');

// ──────────────────────────────────────────────
//  Lifecycle
// ──────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
  // Set default date to today
  if (elDate) {
    const today = new Date();
    elDate.value = today.getFullYear() + '-'
      + String(today.getMonth() + 1).padStart(2, '0') + '-'
      + String(today.getDate()).padStart(2, '0');
  }

  updateConnectionStatus();
  window.addEventListener('online',  () => { updateConnectionStatus(); syncOfflineRecords(); });
  window.addEventListener('offline', updateConnectionStatus);

  if (!IS_GUEST) {
    try {
      await initDB();
      updatePendingBadge();
      syncOfflineRecords();
    } catch (err) {
      console.error('IndexedDB init failed:', err);
    }
  }

  // Bind live dashboard calculations
  [elTruckSold, elAboboyaSold, elFactorySold, elPricePerBag, elFuelExpenses, elOtherExpenses]
    .forEach(input => { if (input) input.addEventListener('input', calculateLiveMetrics); });

  if (elFactoryStatus) {
    elFactoryStatus.addEventListener('change', calculateLiveMetrics);
  }

  calculateLiveMetrics();
});

// ──────────────────────────────────────────────
//  Toast Notification
// ──────────────────────────────────────────────
let toastTimeout;
function showToast(message, isSuccess = true) {
  clearTimeout(toastTimeout);
  elToastMsg.textContent = message;
  const svg = elToast.querySelector('svg');
  if (svg) svg.style.fill = isSuccess ? '#4ADE80' : '#F87171';
  elToast.classList.add('show');
  toastTimeout = setTimeout(() => elToast.classList.remove('show'), 4000);
}

// ──────────────────────────────────────────────
//  Guest Prompt Modal
// ──────────────────────────────────────────────
function showGuestPrompt() {
  // Create and inject a modal if it doesn't exist
  let modal = document.getElementById('guestModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'guestModal';
    modal.style.cssText = `
      position: fixed; inset: 0; background: rgba(0,0,0,0.55);
      z-index: 9999; display: flex; align-items: center; justify-content: center; padding: 20px;
    `;
    modal.innerHTML = `
      <div style="background:white; border-radius:20px; padding:32px 24px; max-width:360px; width:100%;
                  text-align:center; box-shadow:0 25px 60px rgba(0,0,0,0.2);">
        <div style="width:64px;height:64px;background:linear-gradient(135deg,#0B2E6B,#0DAFC4);
                    border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">
          <svg viewBox="0 0 24 24" style="width:30px;height:30px;fill:white;">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
          </svg>
        </div>
        <h3 style="font-size:1.2rem;font-weight:800;color:#0F172A;margin-bottom:8px;">Create Account to Save</h3>
        <p style="font-size:0.85rem;color:#64748B;line-height:1.5;margin-bottom:24px;">
          You're in <strong>Preview Mode</strong>. Create a free account to save your daily records to the database and access them anytime.
        </p>
        <div style="display:flex;flex-direction:column;gap:10px;">
          <a href="/register" style="display:block;background:#0B2E6B;color:white;padding:12px;border-radius:8px;
                              text-decoration:none;font-weight:700;font-size:0.9rem;">
            Create My Account — It's Free
          </a>
          <a href="/login" style="display:block;background:#F1F5F9;color:#334155;padding:12px;border-radius:8px;
                           text-decoration:none;font-weight:600;font-size:0.85rem;">
            I Already Have an Account — Sign In
          </a>
          <button onclick="document.getElementById('guestModal').style.display='none'"
                  style="background:none;border:none;color:#94A3B8;font-size:0.78rem;cursor:pointer;
                         font-family:inherit;padding:4px;font-weight:500;">
            Continue Browsing Preview
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  modal.style.display = 'flex';

  // Close on backdrop click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  }, { once: false });
}

// ──────────────────────────────────────────────
//  Network Status
// ──────────────────────────────────────────────
function updateConnectionStatus() {
  if (!elStatusDot || !elStatusText) return;
  if (navigator.onLine) {
    elStatusDot.classList.remove('offline');
    elStatusText.textContent = 'Online';
  } else {
    elStatusDot.classList.add('offline');
    elStatusText.textContent = 'Offline Mode Active';
  }
}

// ──────────────────────────────────────────────
//  Live Dashboard Calculations
// ──────────────────────────────────────────────
function calculateLiveMetrics() {
  if (!elPricePerBag) return;

  const price       = parseFloat(elPricePerBag.value) || 6.0;
  const truckSold   = parseInt(elTruckSold?.value) || 0;
  const aboboyaSold = parseInt(elAboboyaSold?.value) || 0;
  const factorySold = parseInt(elFactorySold?.value) || 0;
  const fuelExp     = parseFloat(elFuelExpenses?.value) || 0;
  const otherExp    = parseFloat(elOtherExpenses?.value) || 0;

  const totalSold    = truckSold + aboboyaSold + factorySold;
  const totalRevenue = totalSold * price;
  const totalExpenses = fuelExp + otherExp;
  const netCash      = totalRevenue - totalExpenses;

  if (elDashBagsSold) elDashBagsSold.textContent = `${totalSold.toLocaleString()} bags`;
  if (elDashRevenue)  elDashRevenue.textContent  = `GH₵ ${totalRevenue.toFixed(2)}`;
  if (elDashExpenses) elDashExpenses.textContent = `GH₵ ${totalExpenses.toFixed(2)}`;
  if (elDashNetCash)  elDashNetCash.textContent  = `GH₵ ${netCash.toFixed(2)}`;
}

// ──────────────────────────────────────────────
//  IndexedDB (offline storage)
// ──────────────────────────────────────────────
function initDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'date' });
      }
    };
    req.onsuccess = (e) => { db = e.target.result; resolve(); };
    req.onerror   = (e) => reject(e.target.error);
  });
}

function savePendingSync(record) {
  return new Promise((resolve, reject) => {
    const tx    = db.transaction([STORE_NAME], 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req   = store.put(record);
    req.onsuccess = () => resolve();
    req.onerror   = (e) => reject(e.target.error);
  });
}

function getPendingSyncs() {
  return new Promise((resolve, reject) => {
    const tx    = db.transaction([STORE_NAME], 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const req   = store.getAll();
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}

function deletePendingSync(date) {
  return new Promise((resolve, reject) => {
    const tx    = db.transaction([STORE_NAME], 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req   = store.delete(date);
    req.onsuccess = () => resolve();
    req.onerror   = (e) => reject(e.target.error);
  });
}

async function updatePendingBadge() {
  if (!elPendingSyncCount) return;
  try {
    const list = await getPendingSyncs();
    if (list.length > 0) {
      elPendingSyncCount.textContent = `(${list.length} pending sync)`;
      elPendingSyncCount.style.display = 'inline';
    } else {
      elPendingSyncCount.style.display = 'none';
    }
  } catch (err) { console.error(err); }
}

// ──────────────────────────────────────────────
//  Form Submit Handler
// ──────────────────────────────────────────────
if (elForm) {
  elForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Guest / Preview Mode — show account creation prompt
    if (IS_GUEST) {
      showGuestPrompt();
      return;
    }

    const data = {
      date:           elDate.value,
      factory_status: elFactoryStatus.value,
      total_produced:  parseInt(elProduced?.value)      || 0,
      bags_in_storage: parseInt(elStorage?.value)       || 0,
      truck_sent_out:  parseInt(elTruckSent?.value)     || 0,
      truck_sold:      parseInt(elTruckSold?.value)     || 0,
      leakages:        parseInt(elLeakages?.value)      || 0,
      aboboya_sold:    parseInt(elAboboyaSold?.value)   || 0,
      factory_sold:    parseInt(elFactorySold?.value)   || 0,
      price_per_bag:   parseFloat(elPricePerBag?.value) || 6.0,
      fuel_expenses:   parseFloat(elFuelExpenses?.value)  || 0.0,
      other_expenses:  parseFloat(elOtherExpenses?.value) || 0.0,
      cash_withdrawn:  parseFloat(elWithdrawBank?.value)  || 0.0,
      cash_at_hand:    parseFloat(elCashHand?.value)      || 0.0,
      cash_at_bank:    parseFloat(elCashBank?.value)      || 0.0,
      comments: elComments?.value || ''
    };

    // Offline fallback
    if (!navigator.onLine) {
      await saveOffline(data);
      return;
    }

    try {
      const response = await fetch('/api/ledger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(data)
      });

      const resData = await response.json();

      if (response.ok) {
        showToast('✓ Record saved to database successfully!');
        elForm.reset();
        const today = new Date();
        elDate.value = today.getFullYear() + '-'
          + String(today.getMonth() + 1).padStart(2, '0') + '-'
          + String(today.getDate()).padStart(2, '0');
        elPricePerBag.value = '6.0';
        calculateLiveMetrics();
      } else if (resData.error === 'guest_mode') {
        showGuestPrompt();
      } else {
        showToast(resData.error || 'Server error.', false);
      }
    } catch (err) {
      console.warn('Network failed, saving offline:', err);
      await saveOffline(data);
    }
  });
}

// ──────────────────────────────────────────────
//  Offline Save
// ──────────────────────────────────────────────
async function saveOffline(data) {
  if (IS_GUEST) { showGuestPrompt(); return; }
  try {
    data.sync_status = 'pending_sync';
    await savePendingSync(data);
    await updatePendingBadge();
    showToast('Saved to phone memory. Will sync when online.');
    elForm.reset();
    calculateLiveMetrics();
  } catch (e) {
    showToast('Failed to save offline.', false);
  }
}

// ──────────────────────────────────────────────
//  Background Sync
// ──────────────────────────────────────────────
async function syncOfflineRecords() {
  if (!navigator.onLine || !db || IS_GUEST) return;
  try {
    const list = await getPendingSyncs();
    if (list.length === 0) return;

    let count = 0;
    for (const record of list) {
      try {
        const res = await fetch('/api/ledger', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify(record)
        });
        if (res.ok) {
          await deletePendingSync(record.date);
          count++;
        }
      } catch { break; }
    }

    if (count > 0) {
      await updatePendingBadge();
      showToast(`✓ Synced ${count} offline record(s) to database!`);
    }
  } catch (err) {
    console.error('Sync failed:', err);
  }
}
