document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("drawerOverlay");
  const drawer = document.getElementById("orderDrawer");
  const closeBtn = document.getElementById("drawerCloseBtn");

  function closeDrawer() {
    if (drawer) drawer.classList.remove("active");
    if (overlay) overlay.classList.remove("active");
  }

  if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
  if (overlay) overlay.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });

  document.querySelectorAll(".order-trigger").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const orderId = el.getAttribute("data-order-id");
      openOrderDrawer(orderId);
    });
  });

  document.querySelectorAll(".status-change-select").forEach((select) => {
    select.addEventListener("change", async () => {
      const orderId = select.getAttribute("data-order-id");
      const newStatus = select.value;
      const originalValue = select.getAttribute("data-original-status");

      try {
        const res = await fetch(`/api/orders/${orderId}/status`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          alert(data.error || "Status update failed");
          select.value = originalValue;
        } else {
          select.setAttribute("data-original-status", newStatus);
        }
      } catch (err) {
        alert("Failed to communicate with server");
        select.value = originalValue;
      }
    });
  });

  document.querySelectorAll(".stock-form").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const productId = form.getAttribute("data-product-id");
      const input = form.querySelector(".stock-input");
      const btn = form.querySelector("button");
      const val = parseInt(input.value, 10);

      btn.disabled = true;
      try {
        const res = await fetch(`/api/inventory/${productId}/update`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stock: val })
        });
        const json = await res.json();
        if (!res.ok) {
          alert(json.error || "Failed to update stock");
        } else {
          input.value = json.product.stock;
        }
      } catch (err) {
        alert("Error connecting to inventory server");
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll(".active-toggle-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const productId = btn.getAttribute("data-product-id");
      const currentActive = btn.getAttribute("data-active") === "1";
      const nextActive = currentActive ? 0 : 1;

      btn.disabled = true;
      try {
        const res = await fetch(`/api/inventory/${productId}/update`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active: nextActive })
        });
        const json = await res.json();
        if (res.ok && json.success) {
          btn.setAttribute("data-active", nextActive);
          btn.textContent = nextActive === 1 ? "Active" : "Archived";
          if (nextActive === 1) {
            btn.classList.add("btn-dark");
          } else {
            btn.classList.remove("btn-dark");
          }
        }
      } catch (err) {
        alert("Failed to update status");
      } finally {
        btn.disabled = false;
      }
    });
  });

  async function openOrderDrawer(orderId) {
    if (!drawer || !overlay) return;
    overlay.classList.add("active");
    drawer.classList.add("active");

    const drawerBody = document.getElementById("drawerBody");
    const drawerTitle = document.getElementById("drawerOrderNumber");
    drawerTitle.textContent = `Order #${orderId}`;
    drawerBody.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted); font-size:13px;">Loading order record...</div>`;

    try {
      const res = await fetch(`/api/orders/${orderId}`);
      if (!res.ok) {
        drawerBody.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted); font-size:13px;">Error fetching order #${orderId}</div>`;
        return;
      }

      const data = await res.json();
      const o = data.order;
      const items = data.items || [];
      const payments = data.payments || [];
      const inv = data.invoice;

      drawerTitle.textContent = `${o.order_number}`;

      let itemsHtml = items.map((it) => `
        <tr>
          <td class="mono">${escapeHtml(it.sku || "N/A")}</td>
          <td style="font-weight:500;">${escapeHtml(it.product_name)}</td>
          <td class="mono" style="text-align:center;">${it.quantity}</td>
          <td class="mono">Rs. ${parseFloat(it.unit_price).toFixed(2)}</td>
          <td class="mono" style="font-weight:600;">Rs. ${parseFloat(it.total_price).toFixed(2)}</td>
        </tr>
      `).join("");

      let paymentsHtml = payments.length === 0 
        ? `<div style="font-size:12px; color:var(--text-muted);">No payment attempts registered.</div>`
        : payments.map((p) => `
          <div style="border: 1px solid var(--border-default); padding: 12px; border-radius: var(--radius-md); margin-bottom: 8px; background:var(--bg-subtle);">
            <div class="info-grid">
              <span class="info-grid-label">TX UUID:</span>
              <span class="info-grid-val mono" style="font-size:11px;">${escapeHtml(p.transaction_id || "N/A")}</span>
              <span class="info-grid-label">Amount:</span>
              <span class="info-grid-val mono" style="font-weight:600;">${escapeHtml(p.currency || "NPR")} ${parseFloat(p.amount).toFixed(2)}</span>
              <span class="info-grid-label">Status:</span>
              <span class="info-grid-val">
                <span class="pill-badge ${p.status === 'success' ? 'pill-success' : 'pill-pending'}">${escapeHtml(p.status)}</span>
              </span>
              <span class="info-grid-label">Verified:</span>
              <span class="info-grid-val mono" style="font-size:11px;">${escapeHtml(p.verified_at || p.created_at || "N/A")}</span>
            </div>
          </div>
        `).join("");

      drawerBody.innerHTML = `
        <div class="drawer-card">
          <div class="drawer-section-title">Customer Dossier</div>
          <div class="info-grid">
            <span class="info-grid-label">Customer:</span>
            <span class="info-grid-val" style="font-weight:600;">${escapeHtml(o.customer_name || "Unspecified")}</span>
            <span class="info-grid-label">Discord:</span>
            <span class="info-grid-val mono">@${escapeHtml(o.discord_username || "N/A")}</span>
            <span class="info-grid-label">Phone:</span>
            <span class="info-grid-val mono">${escapeHtml(o.delivery_phone || o.customer_phone || "N/A")}</span>
            <span class="info-grid-label">Delivery Addr:</span>
            <span class="info-grid-val">${escapeHtml(o.delivery_address || o.customer_address || "None")}</span>
            <span class="info-grid-label">Map Pin:</span>
            <span class="info-grid-val">
              ${o.delivery_location_link || o.customer_location_link 
                ? `<a href="${encodeURI(o.delivery_location_link || o.customer_location_link)}" target="_blank" rel="noopener noreferrer" style="color:var(--text-main); font-weight:600; text-decoration:none;">Open Location Pin &rarr;</a>` 
                : "None"}
            </span>
          </div>
        </div>

        <div class="drawer-card">
          <div class="drawer-section-title">Purchased Items</div>
          <table class="order-table" style="min-width:auto; font-size:12px;">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th style="text-align:center;">Qty</th>
                <th>Unit</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>${itemsHtml || '<tr><td colspan="5" style="text-align:center; padding:12px; color:var(--text-muted);">No items found</td></tr>'}</tbody>
          </table>
          <div style="text-align:right; margin-top:14px; font-weight:700; font-size:14px;" class="mono">
            Total: Rs. ${parseFloat(o.total_amount).toFixed(2)}
          </div>
        </div>

        <div class="drawer-card">
          <div class="drawer-section-title">Payment Verification</div>
          ${paymentsHtml}
        </div>

        <div class="drawer-card">
          <div class="drawer-section-title">Official Tax Invoice</div>
          ${inv ? `
            <div style="display:flex; align-items:center; justify-content:space-between; border: 1px solid var(--border-default); padding: 12px 14px; border-radius: var(--radius-md); background:var(--bg-subtle);">
              <div>
                <div class="mono" style="font-size:12px; font-weight:600; color:var(--text-main);">${escapeHtml(inv.invoice_number)}</div>
                <div class="mono" style="font-size:11px; color:var(--text-muted); margin-top:2px;">${escapeHtml(inv.created_at)}</div>
              </div>
              <a href="/invoices/${encodeURIComponent(inv.file_path ? inv.file_path.split('/').pop() : '')}" target="_blank" class="btn btn-sm btn-dark">View PDF</a>
            </div>
          ` : `<div style="font-size:12px; color:var(--text-muted);">No invoice generated for this order.</div>`}
        </div>
      `;
    } catch (err) {
      drawerBody.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted); font-size:13px;">Failed to load order dossier.</div>`;
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});