(function(global){
  'use strict';
  const ChatCart = {
    async initializeCart(bot){
      try {
        const url = new URL('/api/cart/get', window.location.origin);
        url.searchParams.set('t', Date.now().toString());
        url.searchParams.set('user_id', bot.userId);
        let res = await fetch(url.toString(), { method: 'GET', headers: { 'Accept':'application/json' }, credentials: 'include' });
        if (!res.ok && res.status !== 200) {
          res = await fetch('/api/cart/get', {
            method: 'POST',
            headers: { 'Content-Type':'application/json', ...(getCSRFToken() ? { 'X-CSRFToken': getCSRFToken() } : {}) },
            body: JSON.stringify({ user_id: bot.userId }),
            credentials: 'include'
          });
        }
        if (res.ok) {
          const data = await res.json();
          if (data && data.cart) { bot.updateCart(data.cart, true); return; }
        }
      } catch (err) { console.error('Cart initialization error:', err); }
      bot.updateCart(null, true);
    },
    async ensureCartLoaded(bot){
      if (bot.cartState && Array.isArray(bot.cartState.items)) return true;
      try {
        const res = await fetch('/api/cart/get', {
          method: 'POST',
          headers: { 'Content-Type':'application/json', ...(getCSRFToken() ? { 'X-CSRFToken': getCSRFToken() } : {}) },
          body: JSON.stringify({ user_id: bot.userId }),
          credentials: 'include'
        });
        const data = await res.json();
        if (data?.cart) { bot.updateCart(data.cart, true); return true; }
      } catch (e) { console.error('ensureCartLoaded error:', e); }
      return false;
    },
    recalculateAndRedrawCart(bot){

      ChatCart.syncPendingCartUpdates(bot);
    },

    async flushCartToServer(bot){
      try{

        const map = Object.assign({}, bot.pendingCartUpdate);
        (Array.isArray(bot.cartState?.items)?bot.cartState.items:[]).forEach(it=>{ map[it.name] = parseInt(it.qty||0,10); });
        bot.pendingCartUpdate = {}; 
        const headers = { 'Content-Type':'application/json', ...(getCSRFToken()?{'X-CSRFToken':getCSRFToken()}:{}), };
        const promises = Object.entries(map).map(([productName, quantity])=>
          fetch('/api/cart/update', {
            method:'POST', headers, credentials:'include',
            body: JSON.stringify({ user_id: bot.userId, product_name: productName, quantity: Math.max(0, parseInt(quantity||0,10)) })
          }).then(r=>r.json()).then(d=>{ if (d?.cart) bot.updateCart(d.cart, true); })
        );
        await Promise.all(promises);
      }catch(e){ console.error('flushCartToServer error', e); }
    },
    optimisticRecalculateAndRedrawCart(bot){

      if (!bot.cartState) return;
      const resolveMembershipPolicy = (mem = {}) => { 
        const tier = String(mem.membership_name || (mem.meta && mem.meta.membership_name) || '').toLowerCase();
        const policy = {
          premium: { rate: 0.10, threshold: 0 },
          gold: { rate: 0.05, threshold: 15000 },
          basic: { rate: 0.00, threshold: 30000 }
        };
        const base = policy[tier] || policy.basic;
        const rate = (mem.discount_rate != null ? Number(mem.discount_rate) : (mem.meta && mem.meta.discount_rate != null ? Number(mem.meta.discount_rate) : base.rate));
        const threshold = (mem.free_shipping_threshold != null ? Number(mem.free_shipping_threshold) : (mem.meta && mem.meta.free_shipping_threshold != null ? Number(mem.meta.free_shipping_threshold) : base.threshold));
        return { rate, threshold };
      };

      try {
        const items = Array.isArray(bot.cartState.items) ? bot.cartState.items : [];
        const subtotal = items.reduce((acc, it) => acc + (parseFloat(it.unit_price||0) * parseInt(it.qty||0, 10)), 0);
        const policy = resolveMembershipPolicy(bot.cartState.membership || {});
        const rate = Number(policy.rate || 0);
        const freeThr = Number(policy.threshold || 0);

        const membershipDiscount = Math.floor(subtotal * rate);
        const effectiveSubtotal = subtotal - membershipDiscount;
        const BASE_SHIPPING = 3000;

        bot.cartState.subtotal = subtotal;
        bot.cartState.shipping_fee = BASE_SHIPPING; 
        bot.cartState.discounts = [];
        if (membershipDiscount > 0) {
          bot.cartState.discounts.push({ type: 'membership_discount', amount: membershipDiscount, description: '멤버십 할인' });
        }
        if (effectiveSubtotal >= freeThr) {

          bot.cartState.discounts.push({ type: 'free_shipping', amount: BASE_SHIPPING, description: '무료배송' });
        }
        const totalDiscount = (bot.cartState.discounts||[]).reduce((a,b)=>a+(b.amount||0),0);
        bot.cartState.total = Math.max(0, subtotal + BASE_SHIPPING - totalDiscount);
      } catch(_) {}
      bot.updateCart(bot.cartState, false);
    },
    handleCartUpdate(bot, productName, action){
      if (!bot.cartState || !bot.cartState.items) return;
      const idx = bot.cartState.items.findIndex(i => i.name === productName);
      if (idx === -1) return;
      switch (action) {
        case 'increment': bot.cartState.items[idx].qty += 1; break;
        case 'decrement': bot.cartState.items[idx].qty -= 1; break;
        case 'remove':    bot.cartState.items[idx].qty  = 0; break;
      }
      const finalQty = bot.cartState.items[idx]?.qty ?? 0;
      if (finalQty <= 0) bot.cartState.items.splice(idx, 1);

      ChatCart.optimisticRecalculateAndRedrawCart(bot);
      clearTimeout(bot.debounceTimer);
      bot.pendingCartUpdate[productName] = Math.max(finalQty, 0);
      bot.debounceTimer = setTimeout(() => ChatCart.syncPendingCartUpdates(bot), 5000);
    },
    syncPendingCartUpdates(bot){
      const updates = bot.pendingCartUpdate; bot.pendingCartUpdate = {};
      if (Object.keys(updates).length === 0) return;
      for (const productName in updates) {
        const quantity = updates[productName];
        fetch('/api/cart/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(getCSRFToken() ? { 'X-CSRFToken': getCSRFToken() } : {}) },
          body: JSON.stringify({ user_id: bot.userId, product_name: productName, quantity }),
          credentials: 'include'
        })
        .then(r => r.json())
        .then(data => { if (!data.error) bot.updateCart(data.cart, true); })
        .catch(err => console.error('Cart sync fetch error:', err));
      }
    },
    updateCart(bot, cart, saveState=true){

      const escapeHtml = (text) => {
        if (bot && typeof bot.escapeHtml === 'function') return bot.escapeHtml(text);
        if (window.UIHelpers && UIHelpers.escapeHtml) return UIHelpers.escapeHtml(text);
        return String(text || '');
      };
      const formatPrice = (price) => {
        if (bot && typeof bot.formatPrice === 'function') return bot.formatPrice(price);
        if (window.UIHelpers && UIHelpers.formatPrice) return UIHelpers.formatPrice(price);
        return String(price || 0);
      };

      const list = document.getElementById('cartItems');
      const previousSelection = new Set();
      if (list) {
        list.querySelectorAll('.cart-select:checked').forEach((node) => {
          if (node.dataset && node.dataset.productName) previousSelection.add(node.dataset.productName);
        });
      }

      if (saveState && cart) {
        if (Array.isArray(cart.items)) {
          cart.items.forEach((item)=>{
            item.qty = parseInt(item.qty, 10);
            item.unit_price = parseFloat(item.unit_price);
          });
        }
        bot.cartState = JSON.parse(JSON.stringify(cart));
      } else if (saveState && !cart) {
        bot.cartState = null;
      }

      const currentCart = bot.cartState;
      const section = document.getElementById('cartSection');
      const countBadge = document.getElementById('cartCount');
      const subtotalEl = document.getElementById('subtotalAmount');
      const discountEl = document.getElementById('discountAmount');
      const totalEl = document.getElementById('totalAmount');
      const shippingFeeEl = document.getElementById('shippingFee');
      const checkoutButton = document.getElementById('checkoutButton');

      if (!section || !list || !countBadge || !subtotalEl || !discountEl || !totalEl || !checkoutButton) return;

      if (!currentCart || !Array.isArray(currentCart.items) || currentCart.items.length === 0) {
        section.classList.remove('hidden');
        list.innerHTML = '<div class="cart-empty p-4 text-center text-gray-500">장바구니가 비어있습니다.</div>';
        countBadge.textContent = '0';
        subtotalEl.textContent = '0원';
        discountEl.textContent = '- 0원';
        totalEl.textContent = '0원';
        if (shippingFeeEl) shippingFeeEl.textContent = '0원';
        checkoutButton.classList.add('hidden');
        ChatCart.recalculateCartTotals(bot, []);
        return;
      }

      section.classList.remove('hidden');
      countBadge.textContent = currentCart.items.length;
      list.innerHTML = '';

      currentCart.items.forEach((item) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'cart-item flex items-center justify-between bg-white rounded p-2 text-sm';
        itemDiv.innerHTML = `
          <div class="flex items-center flex-1 mr-2">
            <input type="checkbox" class="cart-select mr-2" data-product-name="${escapeHtml(item.name)}" />
            <div>
              <span class="font-medium">${escapeHtml(item.name)}</span>
              <div class="text-xs text-gray-500">${formatPrice(item.unit_price)}원</div>
            </div>
          </div>
          <div class="quantity-controls flex items-center">
            <button class="quantity-btn minus-btn" data-product-name="${escapeHtml(item.name)}">-</button>
            <span class="quantity-display">${item.qty}</span>
            <button class="quantity-btn plus-btn" data-product-name="${escapeHtml(item.name)}">+</button>
          </div>
          <button class="remove-item ml-2" data-product-name="${escapeHtml(item.name)}">
            <i class="fas fa-times"></i>
          </button>`;
        list.appendChild(itemDiv);

        const checkbox = itemDiv.querySelector('.cart-select');
        if (previousSelection.has(item.name)) {
          checkbox.checked = true;
        }
        checkbox.addEventListener('change', () => {
          ChatCart.recalculateCartTotals(bot);
        });
      });

      checkoutButton.classList.remove('hidden');
      ChatCart.recalculateCartTotals(bot, previousSelection);
    },

    recalculateCartTotals(bot, preservedSelection){
      const formatPrice = (price) => {
        if (bot && typeof bot.formatPrice === 'function') return bot.formatPrice(price);
        if (window.UIHelpers && UIHelpers.formatPrice) return UIHelpers.formatPrice(price);
        return String(price || 0);
      };

      const subtotalEl = document.getElementById('subtotalAmount');
      const discountEl = document.getElementById('discountAmount');
      const totalEl = document.getElementById('totalAmount');
      const shippingFeeEl = document.getElementById('shippingFee');
      const list = document.getElementById('cartItems');

      if (!subtotalEl || !discountEl || !totalEl || !list) return;

      const selectedNames = new Set();
      list.querySelectorAll('.cart-select').forEach((node) => {
        if (node.checked && node.dataset && node.dataset.productName) {
          selectedNames.add(node.dataset.productName);
        }
      });

      if (!selectedNames.size && preservedSelection && preservedSelection.size) {
        preservedSelection.forEach((name) => selectedNames.add(name));
        list.querySelectorAll('.cart-select').forEach((node) => {
          if (selectedNames.has(node.dataset.productName)) node.checked = true;
        });
      }

      const cartState = bot && bot.cartState ? bot.cartState : { items: [] };
      const items = Array.isArray(cartState.items) ? cartState.items : [];
      const targetedItems = selectedNames.size ? items.filter((item) => selectedNames.has(item.name)) : [];

      const subtotal = targetedItems.reduce((acc, item) => {
        const price = parseFloat(item.unit_price || 0);
        const qty = parseInt(item.qty || 0, 10) || 0;
        return acc + (price * qty);
      }, 0);

      const membership = cartState.membership || {};
      const resolveMembershipPolicy = (mem = {}) => { 
        const tier = String(mem.membership_name || (mem.meta && mem.meta.membership_name) || '').toLowerCase();
        const policy = {
          premium: { rate: 0.10, threshold: 0 },
          gold: { rate: 0.05, threshold: 15000 },
          basic: { rate: 0.00, threshold: 30000 }
        };
        const base = policy[tier] || policy.basic;
        const rate = (mem.discount_rate != null ? Number(mem.discount_rate) : (mem.meta && mem.meta.discount_rate != null ? Number(mem.meta.discount_rate) : base.rate));
        const threshold = (mem.free_shipping_threshold != null ? Number(mem.free_shipping_threshold) : (mem.meta && mem.meta.free_shipping_threshold != null ? Number(mem.meta.free_shipping_threshold) : base.threshold));
        return { rate, threshold };
      };
      const membershipPolicy = resolveMembershipPolicy(membership);
      const rate = Number(membershipPolicy.rate || 0);
      const freeThreshold = Number(membershipPolicy.threshold || 0);
      const baseShippingCost = typeof cartState.shipping_fee === 'number' ? cartState.shipping_fee : 3000;

      const membershipDiscount = targetedItems.length ? Math.floor(subtotal * rate) : 0;
      const extraDiscounts = targetedItems.length && Array.isArray(cartState.discounts)
        ? cartState.discounts
            .filter((d) => d && d.type && d.type !== 'membership_discount' && d.type !== 'free_shipping')
            .reduce((acc, d) => acc + (d.amount || 0), 0)
        : 0;
      const productDiscount = targetedItems.length ? membershipDiscount + extraDiscounts : 0;

      const effectiveSubtotal = subtotal - membershipDiscount;
      const shippingBase = targetedItems.length ? baseShippingCost : 0;
      let shippingDiscount = 0;
      if (targetedItems.length && effectiveSubtotal >= freeThreshold) {
        shippingDiscount = shippingBase;
      }

      const total = targetedItems.length
        ? Math.max(0, subtotal + shippingBase - productDiscount - shippingDiscount)
        : 0;

      subtotalEl.textContent = formatPrice(subtotal) + '원';
      discountEl.textContent = `- ${formatPrice(productDiscount)}원`;
      if (shippingFeeEl) {
        const displayShipping = targetedItems.length ? Math.max(0, shippingBase - shippingDiscount) : 0;
        shippingFeeEl.textContent = formatPrice(displayShipping) + '원';
      }
      totalEl.textContent = formatPrice(total) + '원';
    },
    async handleCheckout(bot){
      if (!bot.cartState||!bot.cartState.items||bot.cartState.items.length===0){ alert('장바구니가 비어있습니다.'); return; }

      try{ clearTimeout(bot.debounceTimer); await ChatCart.flushCartToServer(bot); }catch(_){ }
      const selected = ChatCart.getSelectedCartProducts(bot);
      if (selected.length > 0){
        bot.showCustomLoading('cart','선택한 상품만 결제 중입니다...','progress');
        try {
          const res = await fetch('/api/cart/checkout-selected', {
            method: 'POST',
            headers: { 'Content-Type':'application/json', ...(getCSRFToken() ? { 'X-CSRFToken': getCSRFToken() } : {}) },
            body: JSON.stringify({ user_id: bot.userId, products: selected }),
            credentials: 'include'
          });
          const data = await res.json();
          if (data?.cart) bot.updateCart(data.cart, true);
          if (data && data.order && (data.order.status === 'confirmed' || data.order.order_id)) {
            if (!data.cart || (data.cart.items && data.cart.items.length > 0)) { await ChatCart.initializeCart(bot); }
          }
          if (data?.meta?.final_message) bot.addMessage(data.meta.final_message, 'bot');
          else if (data?.order?.order_id) bot.addMessage(`주문이 완료되었습니다. 주문번호: ${data.order.order_id}`, 'bot');
        } catch (e) { console.error(e); bot.addMessage('선택 결제 중 오류가 발생했습니다.', 'bot', true);
        } finally { bot.hideCustomLoading(); }
        return;
      }
      const message=`장바구니에 있는 상품들로 주문 진행하고 싶어요`;
      bot.addMessage(message,'user'); bot.sendMessage(message, false);
    },
    getSelectedCartProducts(bot){
      const nodes = Array.from(document.querySelectorAll('.cart-select:checked'));

      return nodes.map(n => n.dataset.productName).filter(Boolean);
    },
    async handleRemoveSelected(bot){
      const products = ChatCart.getSelectedCartProducts(bot);
      if (!products.length){ alert('제거할 상품을 선택하세요.'); return; }
      bot.showCustomLoading('cart', '선택한 상품을 장바구니에서 제거 중입니다...', 'dots');
      try {
        const res = await fetch('/api/cart/remove-selected', {
          method: 'POST',
          headers: { 'Content-Type':'application/json', ...(getCSRFToken() ? { 'X-CSRFToken': getCSRFToken() } : {}) },
          body: JSON.stringify({ user_id: bot.userId, products }),
          credentials: 'include'
        });
        const data = await res.json();
        if (data?.cart) bot.updateCart(data.cart, true);
        if (data?.meta?.cart_message) bot.addMessage(data.meta.cart_message, 'bot');
      } catch (err) { console.error(err); bot.addMessage('선택 제거 중 오류가 발생했습니다.', 'bot', true);
      } finally { bot.hideCustomLoading(); }
    },
    async showCartInChat(bot){
      bot.addMessage('장바구니 보여주세요','user');
      if (!bot.cartState||!bot.cartState.items){ await ChatCart.ensureCartLoaded(bot); }
      if (!bot.cartState||!bot.cartState.items||bot.cartState.items.length===0){ bot.addMessage('현재 장바구니가 비어있습니다.','bot'); return; }
      let cartMessage='🛒 현재 장바구니 내용:\n\n';
      bot.cartState.items.forEach((item,i)=>{
        cartMessage+=`${i+1}. ${item.name}\n`;
        cartMessage+=`   수량: ${item.qty}\n`;
        cartMessage+=`   가격: ${UIHelpers.formatPrice(item.unit_price)}원\n`;
        cartMessage+=`   소계: ${UIHelpers.formatPrice(item.unit_price*item.qty)}원\n\n`;
      });
      const discountAmount=(bot.cartState.discounts||[]).reduce((acc,d)=>acc+d.amount,0);
      cartMessage+=`💰 총 상품금액: ${UIHelpers.formatPrice(bot.cartState.subtotal)}원\n`;
      if (discountAmount>0) cartMessage+=`💸 할인금액: -${UIHelpers.formatPrice(discountAmount)}원\n`;
      cartMessage+=`💳 최종 결제금액: ${UIHelpers.formatPrice(bot.cartState.total)}원`;
      bot.addMessage(cartMessage,'bot');
    }
  };

  global.ChatCart = ChatCart;
})(window);
