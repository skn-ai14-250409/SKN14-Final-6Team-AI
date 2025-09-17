class ChatBot {
  constructor() {
    this.sessionId = 'sess_' + Math.random().toString(36).substr(2, 9);
    this.userId = resolveUserId();
    this.cartState = null;

    this.productCandidates = [];
    this.productPage = 0;
    this.PRODUCTS_PER_PAGE = 5;
    
    this.ingredientCandidates = [];
    this.ingredientPage = 0;
    this.INGREDIENTS_PER_PAGE = 5;

    this.productSortBy = 'popular';
    this.ingredientSortBy = 'popular';

    this.debounceTimer = null;
    this.pendingCartUpdate = {};

    this.isRecording = false;
    this.canceled = false;
    this.recognition = null;
    this.mediaRecorder = null;
    this.mediaStream = null;
    this.audioChunks = [];
    this.lastTranscript = '';

    this.pendingEvidence = null;
    this.evidenceInput = null;
    this.lastOrdersKey = null;
    
    this.isCurrentlyDeliveryInquiry = false;
    this.lastRenderedDate = null;

    this.init();
    try { window._chatbot = this; window.chatbot = this; } catch(_) {}
  }

  init() {
    this.bindEvents();
    try { if (window.CSEvidence && typeof CSEvidence.setup === 'function') CSEvidence.setup(this); } catch (_) {}
    this.updateSessionInfo();
      if (window.ChatCart) ChatCart.initializeCart(this);
    try {
      const bootKey = `chat_session_boot_${this.userId}`;
      if (!sessionStorage.getItem(bootKey)) {
        localStorage.removeItem(`chat_messages_${this.userId}`);
        localStorage.removeItem(`chat_session_${this.userId}`);
        localStorage.removeItem(`chat_pending_message_${this.userId}`);
        sessionStorage.setItem(bootKey, '1');
      }
    } catch (_) {}
    this.restoreChatState();
    try { this.renderFavorites(); } catch(_) {}
    this.hideCustomLoading();
  }

  bindEvents() {
    document.getElementById('chatForm')
      .addEventListener('submit', (e) => { e.preventDefault(); this.sendMessage(); });

    document.getElementById('messageInput')
      .addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
      });

    document.querySelectorAll('.quick-action').forEach(btn => {
      btn.addEventListener('click', () => {
        const message = btn.dataset.message;
        if (message === '장바구니 보여주세요') { this.showCartInChat(); return; }
        this.addMessage(message, 'user');
        document.getElementById('messageInput').value = message;
        this.sendMessage(message);
      });
    });

    document.getElementById('clearChat').addEventListener('click', () => this.clearChat());

    document.getElementById('cartItems').addEventListener('click', (e) => {
      const button = e.target.closest('button'); if (!button) return;
      const productName = button.dataset.productName;
      let action;
      if (button.classList.contains('plus-btn')) action = 'increment';
      else if (button.classList.contains('minus-btn')) action = 'decrement';
      else if (button.classList.contains('remove-item')) action = 'remove';
      if (action && window.ChatCart) ChatCart.handleCartUpdate(this, productName, action);
    });

    document.getElementById('checkoutButton').addEventListener('click', () => { if (window.ChatCart) ChatCart.handleCheckout(this); });

    const micBtn = document.getElementById('voiceInput');
    const cancelBtn = document.getElementById('voiceCancel');
    if (micBtn) micBtn.addEventListener('click', () => { if (window.ChatVoice) ChatVoice.toggleVoiceRecording(this); });
    if (cancelBtn) cancelBtn.addEventListener('click', () => { if (window.ChatVoice) ChatVoice.cancelVoiceRecording(this); });

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('button.input-btn');
      if (btn && btn.querySelector('i.fas.fa-headset')) {e.preventDefault(); this.handleConsultantConnect();
      } 
    });

    document.addEventListener('click', (e) => { if (window.ChatCS) return ChatCS.handleOrderSelectClick(this, e); });
    document.addEventListener('click', (e) => { if (window.ChatCS) return ChatCS.handleShowMoreOrders(this, e); });

    document.addEventListener('click', (e) => { if (window.ChatCS) return ChatCS.handleOrderItemClick(this, e); });
    document.addEventListener('click', (e) => { if (window.ChatCS) return ChatCS.handleEvidenceUploadButtonClick(this, e); });

    document.addEventListener('click', (e) => this.handleClampToggle(e));

    document.addEventListener('click', (e) => {
      const favRemove = e.target.closest('.chat-fav-remove');
      if (favRemove){
        const url = favRemove.getAttribute('data-url')||'';
        const title = favRemove.getAttribute('data-title')||'';
        if (url) this.removeFavoriteRecipe({ url, title });
        return;
      }
      const favIng = e.target.closest('.chat-fav-ingredients');
      if (favIng){
        const title = favIng.getAttribute('data-title')||'';
        const desc = favIng.getAttribute('data-desc')||'';
        const url = favIng.getAttribute('data-url')||'';
        if (window.ChatRecipes) return ChatRecipes.requestRecipeIngredients(this, { title, description: desc, url });
      }
    });
  }

  sortProducts(products, sortBy) {
    if (!products || products.length === 0) return products;
    
    const sortedProducts = [...products];
    
    switch (sortBy) {
      case 'price_low':
        return sortedProducts.sort((a, b) => (a.price || 0) - (b.price || 0));
      case 'price_high':
        return sortedProducts.sort((a, b) => (b.price || 0) - (a.price || 0));
      case 'name':
        return sortedProducts.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'ko'));
      case 'popular':
      default:
        return sortedProducts;
    }
  }

  sortIngredients(ingredients, sortBy) {
    if (!ingredients || ingredients.length === 0) return ingredients;
    
    const sortedIngredients = [...ingredients];
    
    switch (sortBy) {
      case 'price_low':
        return sortedIngredients.sort((a, b) => (a.price || 0) - (b.price || 0));
      case 'price_high':
        return sortedIngredients.sort((a, b) => (b.price || 0) - (a.price || 0));
      case 'name':
        return sortedIngredients.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'ko'));
      case 'popular':
      default:
        return sortedIngredients;
    }
  }

  handleProductSortChange(newSortBy) {
    if (window.ChatProducts) return ChatProducts.handleProductSortChange(this, newSortBy);
  }

  handleIngredientSortChange(newSortBy) {
    this.ingredientSortBy = newSortBy;
    this.ingredientPage = 0;
    this._renderIngredientsPage();
  }

  createSortSelectBox(currentSortBy, onChangeCallback, elementId) {
    const sortOptions = [
      { value: 'popular', label: '인기순' },
      { value: 'price_low', label: '가격 낮은순' },
      { value: 'price_high', label: '가격 높은순' },
    ];

    const selectHtml = `
      <div class="flex items-center justify-between mb-3">
        <span class="text-sm font-medium text-gray-700">정렬 기준</span>
        <select id="${elementId}" class="sort-select text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:border-green-500 focus:outline-none">
          ${sortOptions.map(option => 
            `<option value="${option.value}" ${currentSortBy === option.value ? 'selected' : ''}>${option.label}</option>`
          ).join('')}
        </select>
      </div>`;

    return { html: selectHtml, bindEvent: (container) => {
      const selectElement = container.querySelector(`#${elementId}`);
      if (selectElement) {
        selectElement.addEventListener('change', (e) => {
          onChangeCallback(e.target.value);
        });
      }
    }};
  }

  _renderPaginatedList(config) {
    const { 
      listElement, 
      dataArray, 
      currentPage, 
      itemsPerPage, 
      renderItemCallback, 
      onPageChange,
      bulkActionConfig = null,
      sortConfig = null
    } = config;

    listElement.innerHTML = '';

    if (sortConfig) {
      const sortContainer = document.createElement('div');
      sortContainer.className = 'sort-container mb-0 p-1 bg-gray-50 rounded-lg';
      sortContainer.innerHTML = sortConfig.html;
      listElement.appendChild(sortContainer);
      
      if (sortConfig.bindEvent) {
        sortConfig.bindEvent(sortContainer);
      }
    }

    const totalItems = dataArray.length;
    const totalPages = Math.ceil(totalItems / itemsPerPage);

    let validPage = currentPage;
    if (validPage < 0) validPage = 0;
    if (validPage >= totalPages) validPage = totalPages - 1;
    
    const start = validPage * itemsPerPage;
    const pageItems = dataArray.slice(start, start + itemsPerPage);

    pageItems.forEach((item, index) => {
      const globalIndex = start + index;
      const itemElement = renderItemCallback(item, globalIndex);
      listElement.appendChild(itemElement);
    });

    if (totalPages > 1) {
      const paginationDiv = document.createElement('div');
      paginationDiv.className = 'flex items-center justify-center space-x-2 mt-3';

      const prevBtn = document.createElement('button');
      prevBtn.innerHTML = '<i class="fas fa-chevron-left"></i>';
      prevBtn.className = 'pagination-btn px-2 py-1 text-xs border rounded hover:bg-gray-100 disabled:opacity-50';
      if (validPage === 0) {
        prevBtn.disabled = true;
      }
      prevBtn.addEventListener('click', () => {
        onPageChange(validPage - 1);
      });

      const pageInfo = document.createElement('span');
      pageInfo.className = 'text-xs font-medium text-gray-600 px-2';
      pageInfo.textContent = `${validPage + 1} / ${totalPages}`;

      const nextBtn = document.createElement('button');
      nextBtn.innerHTML = '<i class="fas fa-chevron-right"></i>';
      nextBtn.className = 'pagination-btn px-2 py-1 text-xs border rounded hover:bg-gray-100 disabled:opacity-50';
      if (validPage === totalPages - 1) {
        nextBtn.disabled = true;
      }
      nextBtn.addEventListener('click', () => {
        onPageChange(validPage + 1);
      });

      paginationDiv.appendChild(prevBtn);
      paginationDiv.appendChild(pageInfo);
      paginationDiv.appendChild(nextBtn);
      listElement.appendChild(paginationDiv);
    }

    if (bulkActionConfig) {
      const bulkContainer = document.createElement('div');
      bulkContainer.className = 'mt-4 p-3 bg-gray-50 rounded-lg';
      bulkContainer.innerHTML = bulkActionConfig.html;
      listElement.appendChild(bulkContainer);

      if (bulkActionConfig.events) {
        bulkActionConfig.events.forEach(event => {
          const element = bulkContainer.querySelector(event.selector);
          if (element) {
            element.addEventListener(event.type, event.handler);
          }
        });
      }
    }
  }

  _renderProductPage() {
    if (window.ChatProducts) return ChatProducts._renderProductPage(this);
  }

  sendMessage(messageOverride, silent) {
    if (typeof messageOverride === 'undefined') messageOverride = null;
    if (typeof silent === 'undefined') silent = false;
    const input = document.getElementById('messageInput');
    const message = messageOverride || (input ? input.value.trim() : '');
    if (!message) return Promise.resolve(null);
    try {
      const m = (message||'').toLowerCase();
      if ((m.includes('결제') || m.includes('주문') || m.includes('checkout')) && window.ChatCart && typeof ChatCart.flushCartToServer === 'function') {
        if (this.pendingCartUpdate && Object.keys(this.pendingCartUpdate).length > 0) { clearTimeout(this.debounceTimer); }
        ChatCart.flushCartToServer(this);
      }
    } catch(_) {}
    if (!silent && !messageOverride) this.addMessage(message, 'user');
    if (input) input.value = '';
    if (!silent) this.showSmartLoading(message);
    var headers = { 'Content-Type':'application/json' };
    var csrf = getCSRFToken && getCSRFToken(); if (csrf) headers['X-CSRFToken'] = csrf;
    return fetch('/api/chat', {
      method: 'POST', headers: headers, credentials: 'include',
      body: JSON.stringify({ message: message, user_id: this.userId, session_id: this.sessionId })
    })
    .then((response) => response.json().then((data)=>({response,data})))
    .then(async ({response, data}) => {
      if (!response.ok) throw new Error(data.detail || 'API 호출 실패');
      this.sessionId = data.session_id;
      const hasOrderPicker = !!(data.cs && Array.isArray(data.cs.orders) && data.cs.orders.length);
      if (!silent && data.response && !hasOrderPicker) this.addMessage(data.response, 'bot');
      this.updateSidebar(data);
      try {
        if (data && data.order && (data.order.status === 'confirmed' || data.order.order_id)) {
          if (!data.cart || (data.cart.items && data.cart.items.length > 0)) {
            if (window.ChatCart) { const p = ChatCart.initializeCart(this); if (p && typeof p.then === 'function') await p; }
          }
        }
      } catch(_) {}
      this.updateSessionInfo(data.metadata);
      return data;
    })
    .catch((error)=>{
      console.error('Error:', error);
      if (!silent) this.addMessage('죄송합니다. 일시적인 오류가 발생했습니다.', 'bot', true);
      return null;
    })
    .finally(()=>{ this.hideCustomLoading(); });
  }

  formatBotMessage(content) {
    if (isLikelyHtml(content)) return content;
    if (window.QMarkdown && typeof window.QMarkdown.render === 'function') {
      try { return window.QMarkdown.render(String(content||'')); } catch (_) {}
    }
    const div = document.createElement('div');
    div.textContent = content || '';
    return div.innerHTML.replace(/\n/g, '<br>');
  }

  addMessage(content, sender, isError) {
    if (typeof isError === 'undefined') isError = false;
    const messagesContainer = document.getElementById('messages');
    const today = new Date();
    const dstr = today.getFullYear()+ '-' + String(today.getMonth()+1).padStart(2,'0')+ '-' + String(today.getDate()).padStart(2,'0');
    if (this.lastRenderedDate !== dstr){
      const sep = document.createElement('div');
      sep.className = 'text-center my-2';
      sep.innerHTML = `<span class="inline-block text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">${dstr}</span>`;
      messagesContainer.appendChild(sep);
      this.lastRenderedDate = dstr;
    }
    const messageDiv = document.createElement('div');
    messageDiv.className = 'mb-4 message-animation';

    if (sender === 'user') {
      messageDiv.innerHTML = `
        <div class="flex items-end justify-end">
          <div class="message-bubble-user mr-2">${this.escapeHtml(content)}</div>
          <div class="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center flex-shrink-0">
            <i class="fas fa-user text-white text-sm"></i>
          </div>
        </div>`;
      messagesContainer.appendChild(messageDiv);
      this.scrollToBottom();
      this.persistChatState();
      return;
    }

    const isHtml = isLikelyHtml(content);
    const html = this.formatBotMessage(content);
    const needClamp = !isHtml && this.needsClamp(html);

    const inner = document.createElement('div');
    inner.innerHTML = `
      <div class="flex items-start">
        <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
          <i class="fas fa-robot text-green-600 text-sm"></i>
        </div>
        <div class="message-bubble-bot ${isError ? 'error' : ''}">
          <div class="bot-text">${html}</div>
          ${needClamp ? '<button class="text-xs text-gray-500 mt-2 hover:underline" data-action="expand">더보기</button>' : ''}
        </div>
      </div>
    `;
    messageDiv.appendChild(inner);
    messagesContainer.appendChild(messageDiv);

    if (needClamp) {
      const textEl = messageDiv.querySelector('.bot-text');
      textEl.dataset.expanded = 'false';
      this.applyClamp(textEl, true);
    }

    this.scrollToBottom();
    this.persistChatState();
  }

  renderFavorites(){
    const section = document.getElementById('favoritesSection');
    if (!section) return;
    const target = section.querySelector('#favoritesListInChat') || (()=>{ const d=document.createElement('div'); d.id='favoritesListInChat'; section.innerHTML=''; section.appendChild(d); return d; })();
    const render = (items)=>{
      if (!Array.isArray(items) || items.length===0){
        target.innerHTML = '<div class="empty-state"><i class="fas fa-star text-gray-300 text-4xl mb-4"></i><p class="text-gray-500">저장된 레시피가 없습니다</p></div>';
        return;
      }
      target.innerHTML = items.map(r=>{
        const title = this.escapeHtml(r.title||r.recipe_title||'레시피');
        const desc = this.escapeHtml(r.description||r.snippet||'');
        const url = r.url||r.recipe_url||'#';
        const cooking = this.escapeHtml(r.cooking_time||'');
        const servings = this.escapeHtml(r.servings||'');
        return `
          <div class="recipe-card bg-white rounded-lg p-3 border hover:shadow-md transition cursor-pointer mb-2">
            <div class="recipe-card-body">
              <h4 class="font-semibold text-gray-800 mb-2">${title}</h4>
              <p class="text-gray-600 mb-2 text-xs">${desc}</p>
              <div class="flex items-center justify-between">
                <div class="recipe-info flex gap-3 text-xs text-gray-500">
                  ${cooking?`<span><i class=\"fas fa-clock mr-1\"></i>${cooking}</span>`:''}
                  ${servings?`<span><i class=\"fas fa-user mr-1\"></i>${servings}</span>`:''}
                </div>
                <div class="flex items-center gap-2">
                  <button class="chat-fav-ingredients bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-1 rounded text-xs font-medium transition" data-title="${this.escapeHtml(r.title||r.recipe_title||'')}" data-desc="${this.escapeHtml(r.description||r.snippet||'')}" data-url="${this.escapeHtml(url)}">
                    <i class="fas fa-shopping-basket mr-1"></i>재료 추천받기
                  </button>
                  <button class="chat-fav-remove px-2 py-1 text-xs border rounded hover:bg-gray-50" title="즐겨찾기 삭제" data-url="${this.escapeHtml(url)}" data-title="${this.escapeHtml(r.title||r.recipe_title||'')}">
                    <i class="fas fa-trash-alt"></i>
                  </button>
                </div>
              </div>
            </div>
          </div>`;
      }).join('');
    };
    const localItems = (()=>{ try { return JSON.parse(localStorage.getItem(this.getFavoritesKey())||'[]'); } catch(_) { return []; } })();
    fetch(`/api/recipes/favorites?user_id=${encodeURIComponent(this.userId)}`, { credentials:'include' })
      .then(r=>r.json()).then(async data=>{
        const serverItems = (data && data.items) ? data.items.map(x=>({ title:x.recipe_title, url:x.recipe_url, description:x.snippet })) : [];
        if (serverItems.length===0 && Array.isArray(localItems) && localItems.length>0){
          try{
            await fetch('/api/recipes/favorites/bulk-sync',{
              method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
              body: JSON.stringify({ user_id:this.userId, items: localItems.map(x=>({ user_id:this.userId, recipe_url:x.url, recipe_title:x.title, snippet:x.description||'' })) })
            });
            const r2 = await fetch(`/api/recipes/favorites?user_id=${encodeURIComponent(this.userId)}`, { credentials:'include' });
            const d2 = await r2.json();
            render((d2.items||[]).map(x=>({ title:x.recipe_title, url:x.recipe_url, description:x.snippet })));
            return;
          }catch(e){ console.error('favorites bulk-sync error', e); }
        }
        render(serverItems);
      }).catch(()=> render(localItems));

    target.addEventListener('click', (e)=>{
      const btn = e.target.closest('.chat-fav-ingredients');
      if (!btn) return;
      e.stopPropagation();
      if (window.ChatRecipes) ChatRecipes.requestRecipeIngredients(this, { title: btn.dataset.title||'', description: btn.dataset.desc||'', url: btn.dataset.url||'' });
    });
  }

  needsClamp(html) { return (window.UIHelpers && UIHelpers.needsClamp) ? UIHelpers.needsClamp(html) : false; }
  applyClamp(el, clamp) { if (window.UIHelpers && UIHelpers.applyClamp) UIHelpers.applyClamp(el, clamp); }

  handleClampToggle(e) {
    const btn = e.target.closest('button[data-action="expand"], button[data-action="collapse"]');
    if (!btn) return;
    const bubble = btn.closest('.message-bubble-bot');
    if (!bubble) return;
    const textEl = bubble.querySelector('.bot-text');
    if (!textEl) return;

    const expanded = textEl.dataset.expanded === 'true';
    if (expanded) {
      this.applyClamp(textEl, true);
      textEl.dataset.expanded = 'false';
      btn.dataset.action = 'expand';
      btn.textContent = '더보기';
    } else {
      this.applyClamp(textEl, false);
      textEl.dataset.expanded = 'true';
      btn.dataset.action = 'collapse';
      btn.textContent = '접기';
    }
    this.scrollToBottom();
  }

  addImageMessage(src, sender) {
    if (typeof sender === 'undefined') sender = 'user';
    const messagesContainer = document.getElementById('messages');
    const wrapper = document.createElement('div');
    wrapper.className = 'mb-4 message-animation';
    const bubbleCommon = 'max-w-xs rounded-2xl overflow-hidden border';
    const imgHtml = `<img src="${src}" alt="uploaded" class="block w-full h-auto">`;
    if (sender === 'user') {
      wrapper.innerHTML = `
        <div class="flex items-end justify-end">
          <div class="mr-2 ${bubbleCommon}">${imgHtml}</div>
          <div class="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center flex-shrink-0">
            <i class="fas fa-user text-white text-sm"></i>
          </div>
        </div>`;
    } else {
      wrapper.innerHTML = `
        <div class="flex items-start">
          <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
            <i class="fas fa-robot text-green-600 text-sm"></i>
          </div>
          <div class="${bubbleCommon}">${imgHtml}</div>
        </div>`;
    }
    messagesContainer.appendChild(wrapper);
    this.scrollToBottom();
    this.persistChatState();
  }

  showTyping(){ document.getElementById('loadingIndicator').classList.remove('hidden'); this.scrollToBottom(); }
  hideTyping(){ document.getElementById('loadingIndicator').classList.add('hidden'); }

  showCustomLoading(type, message, animationType) {
    if (typeof animationType === 'undefined') animationType = 'dots';
    this.hideCustomLoading();

    const messagesContainer = document.getElementById('messages');
    const wrapper = document.createElement('div');
    wrapper.id = 'loadingIndicator';
    wrapper.className = 'mb-4 message-animation';

    const loadingConfigs = {
      search:  { icon: 'fas fa-search rotating-icon',  colorClass: 'loading-search',  message: message || '상품을 검색 중입니다...' },
      recipe:  { icon: 'fas fa-utensils loading-icon', colorClass: 'loading-recipe',  message: message || '레시피를 검색 중입니다...' },
      cart:    { icon: 'fas fa-shopping-cart loading-icon', colorClass: 'loading-cart', message: message || '장바구니를 업데이트 중입니다...' },
      cs:      { icon: 'fas fa-headset loading-icon', colorClass: 'loading-cs', message: message || '문의 내용을 확인 중입니다...' },
      popular: { icon: 'fas fa-search rotating-icon', colorClass: 'loading-search', message: message || '상품을 검색 중입니다...' }
    };
    const config = loadingConfigs[type] || loadingConfigs['search'];

    wrapper.innerHTML = `
      <div class="flex items-start">
        <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
          <i class="${config.icon} ${config.colorClass}"></i>
        </div>
        <div class="message-bubble-bot">
          <div class="flex items-center">
            <span>${config.message}</span>
          </div>
          <div class="mt-2 flex space-x-1">
            <div class="w-2 h-2 bg-green-500 rounded-full animate-bounce"></div>
            <div class="w-2 h-2 bg-green-500 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
            <div class="w-2 h-2 bg-green-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
          </div>
        </div>
      </div>
    `;

    messagesContainer.appendChild(wrapper);
    this.scrollToBottom();
  }

  hideCustomLoading() {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) indicator.remove();
  }

  showSmartLoading(message){
    const msg=message.toLowerCase();
    if (msg.includes('인기')||msg.includes('추천')) { this.showCustomLoading('search','상품 정보를 검색 중입니다...','progress'); return; }
    if (msg.includes('레시피')||msg.includes('요리')||msg.includes('만들')||msg.includes('조리')) { this.showCustomLoading('recipe','맛있는 레시피를 검색 중입니다...','pulse'); return; }
    if (msg.includes('장바구니')||msg.includes('담아')||msg.includes('주문')) { this.showCustomLoading('cart','장바구니 정보를 확인 중입니다...','dots'); return; }
    if (msg.includes('문의')||msg.includes('배송')||msg.includes('환불')||msg.includes('교환')||msg.includes('탈퇴')) { this.showCustomLoading('cs','고객지원 정보를 찾고 있습니다...','dots'); return; }
    this.showCustomLoading('search','상품 정보를 검색 중입니다...','progress');
  }

  scrollToBottom(){
    const messages = document.getElementById('messages');
    if (messages) {
      messages.scrollTop = messages.scrollHeight;
    }
    const c = document.getElementById('chatContainer');
    if (c) {
      c.scrollTop = c.scrollHeight;
    }
  }

  updateSidebar(data){
    if (data.search && data.search.candidates) {
      if (window.ChatProducts) ChatProducts.updateProductsList(this, data.search.candidates);
    } else {
      document.getElementById('productsSection').classList.add('hidden');
    }
    
    if (window.ChatRecipes) ChatRecipes.updateRecipesList(this, data.recipe);
    if (data.cart) this.updateCart(data.cart,true);
    this.updateOrderInfo(data.order);
    if (window.ChatCS) ChatCS.updateCS(this, data.cs);
  }


  getFavoritesKey(){ return `favorite_recipes_${this.userId}`; }
  loadFavoriteRecipes(){ try{ return JSON.parse(localStorage.getItem(this.getFavoritesKey())||'[]'); }catch(_){ return []; } }
  saveFavoriteRecipe(item){
    return fetch('/api/recipes/favorites',{
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({
        user_id: this.userId,
        recipe_url: item.url||item.recipe_url,
        recipe_title: item.title||item.recipe_title,
        snippet: item.description||item.snippet||'',
        source: 'tavily'
      })
    }).then(r=>r.json()).then((data)=>{
      if (data && data.code==='already_exists') this.addMessage('이미 저장된 레시피입니다','bot');
      const list=this.loadFavoriteRecipes(); list.unshift(item);
      localStorage.setItem(this.getFavoritesKey(), JSON.stringify(this.dedupeRecipes(list)));
      try { this.renderFavorites(); } catch(_) {}
      try { if (item && (item.title||item.recipe_title)) this.addMessage(`"${item.title||item.recipe_title}"을(를) 즐겨찾기에 추가했습니다.`, 'bot'); } catch(_) {}
    }).catch(e=>console.error('saveFavoriteRecipe error', e));
  }
  removeFavoriteRecipe(item){
    return fetch('/api/recipes/favorites',{
      method:'DELETE', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({ user_id: this.userId, recipe_url: item.url||item.recipe_url })
    }).then(r=>r.json()).then((data)=>{
      if (data && data.code==='already_removed') this.addMessage('이미 제거된 레시피 입니다','bot');
    }).catch(e=>console.error('removeFavoriteRecipe error', e)).finally(()=>{
      const list=this.loadFavoriteRecipes().filter(x=>x.url!==item.url && x.title!==item.title);
      localStorage.setItem(this.getFavoritesKey(), JSON.stringify(list));
      try { this.renderFavorites(); } catch(_) {}
      try { if (item && (item.title||item.recipe_title)) this.addMessage(`"${item.title||item.recipe_title}"을(를) 즐겨찾기에서 제거했습니다.`, 'bot'); } catch(_) {}
    });
  }
  dedupeRecipes(list){
    const seen = new Set();
    const out = [];
    for (const r of list){
      const key = (r.url && String(r.url).trim()) || (r.title && String(r.title).trim()) || JSON.stringify(r);
      if (!seen.has(key)) { seen.add(key); out.push(r); }
    }
    return out;
  }

renderEvidenceResultBubble(data, ctx){
  const cs = (data && data.cs) || {};
  const ticket = cs.ticket || {};
  const analysis = ticket.image_analysis || {};

  const prod = this.escapeHtml(ticket.product || ctx.product || "");
  const tId  = this.escapeHtml(ticket.ticket_id || "");
  const agentMsg = this.escapeHtml(ticket.agent_message || cs.message || "");

  const reason = this.escapeHtml(analysis.human_reason || analysis.issue_summary || "");
  let issues = "";
  if (Array.isArray(analysis.quality_issues)) {
    issues = this.escapeHtml(analysis.quality_issues.join(", "));
  } else if (analysis.quality_issues) {
    issues = this.escapeHtml(String(analysis.quality_issues));
  }
  const conf = (analysis.confidence != null)
    ? `신뢰도 ${Math.round(Number(analysis.confidence)*100)}%`
    : "";

  let topLine = "";
  if (tId) {
    topLine = `
      <div class="text-sm">
        "<span class="font-medium">${prod}</span>" 상품
        <span class="font-semibold text-green-600">환불 접수 완료</span>
        <span class="text-xs text-gray-500 ml-2">티켓번호: <span class="font-mono">${tId}</span></span>
      </div>`;
  } else if (prod) {
    topLine = `<div class="text-sm">"${prod}"에 대한 접수 결과</div>`;
  }

  const agentBlock = agentMsg
    ? `<div class="text-sm leading-relaxed mt-1">${agentMsg}</div>`
    : "";

  const detailsBlock = `
    ${reason ? `<div class="text-xs mt-2"><span class="text-gray-500">사유</span> · ${reason}</div>` : ""}
    ${issues ? `<div class="text-xs mt-1"><span class="text-gray-500">감지된 이슈</span> · ${issues}${conf ? ` (${conf})` : ""}</div>` : ""}
  `;

  const html = `
    <div class="order-evidence-result rounded-lg border p-3">
      ${topLine}
      ${agentBlock}
      ${detailsBlock}
    </div>
  `;
  this.addMessage(html, 'bot');
  this.lastCSOrderListKey = null;
  this.lastCSOrderListTs  = 0;
}

  updateCart(cart, saveState = true){
    if (saveState && cart) {
      if (cart.items) { cart.items.forEach(item=>{ item.qty=parseInt(item.qty,10); item.unit_price=parseFloat(item.unit_price); }); }
      this.cartState=JSON.parse(JSON.stringify(cart));
    }
    const currentCart=this.cartState;
    const section=document.getElementById('cartSection');
    const list=document.getElementById('cartItems');
    const countBadge=document.getElementById('cartCount');
    const subtotalEl=document.getElementById('subtotalAmount');
    const discountEl=document.getElementById('discountAmount');
    const totalEl=document.getElementById('totalAmount');
    const shippingFeeEl=document.getElementById('shippingFee');
    const checkoutButton=document.getElementById('checkoutButton');

    if (!currentCart||!currentCart.items||currentCart.items.length===0){
      section.classList.remove('hidden'); list.innerHTML=`<div class="cart-empty p-4 text-center text-gray-500">장바구니가 비어있습니다.</div>`;
      countBadge.textContent='0'; subtotalEl.textContent='0원'; discountEl.textContent='- 0원'; totalEl.textContent='0원'; checkoutButton.classList.add('hidden'); return;
    }

    section.classList.remove('hidden'); countBadge.textContent=currentCart.items.length; list.innerHTML='';
    currentCart.items.forEach(item=>{
      const itemDiv=document.createElement('div');
      itemDiv.className='cart-item flex items-center justify-between bg-white rounded p-2 text-sm';
      itemDiv.innerHTML=`
        <div class="flex items-center flex-1 mr-2">
          <input type="checkbox" class="cart-select mr-2" data-product-name="${this.escapeHtml(item.name)}" />
          <div>
            <span class="font-medium">${this.escapeHtml(item.name)}</span>
            <div class="text-xs text-gray-500">${this.formatPrice(item.unit_price)}원</div>
          </div>
        </div>
        <div class="quantity-controls flex items-center">
          <button class="quantity-btn minus-btn" data-product-name="${this.escapeHtml(item.name)}">-</button>
          <span class="quantity-display">${item.qty}</span>
          <button class="quantity-btn plus-btn" data-product-name="${this.escapeHtml(item.name)}">+</button>
        </div>
        <button class="remove-item ml-2" data-product-name="${this.escapeHtml(item.name)}">
          <i class="fas fa-times"></i>
        </button>`;
      list.appendChild(itemDiv);
    });

    subtotalEl.textContent=this.formatPrice(currentCart.subtotal)+'원';
    const productDiscountAmount=(currentCart.discounts||[]).filter(d=>d.type!=='free_shipping').reduce((acc,d)=>acc+(d.amount||0),0);
    discountEl.textContent=`- ${this.formatPrice(productDiscountAmount)}원`;
    const hasFreeShip = (currentCart.discounts||[]).some(d=>d.type==='free_shipping');
    const displayShipping = hasFreeShip ? 0 : (currentCart.shipping_fee||0);
    if (shippingFeeEl) shippingFeeEl.textContent=this.formatPrice(displayShipping)+'원';
    totalEl.textContent=this.formatPrice(currentCart.total)+'원';
    checkoutButton.classList.remove('hidden');
  }

  updateOrderInfo(order){
    const section = document.getElementById('orderSection');
    const info = document.getElementById('orderInfo');
    if (!section || !info) return;
    if (!order || !order.order_id) {
      section.classList.add('hidden');
      info.innerHTML = '';
      return;
    }
    section.classList.remove('hidden');
    info.innerHTML = `
      <p><strong>주문번호:</strong> ${this.escapeHtml(order.order_id)}</p>
      <p><strong>총 금액:</strong> ${this.formatPrice(order.total_amount)}원</p>
      <p><strong>상태:</strong> <span class="font-bold text-blue-600">${order.status==='confirmed'?'주문완료':'처리중'}</span></p>`;
  }

  updateSessionInfo(){ const sessionInfo=document.getElementById('sessionInfo'); if (this.sessionId) sessionInfo.textContent=`세션: ${this.sessionId.slice(-8)}`; }

  clearChat(){
    if (confirm('채팅 기록을 모두 지우시겠습니까?')) {
      document.getElementById('messages').innerHTML='';
      this.sessionId='sess_'+Math.random().toString(36).substr(2,9);
      this.updateSessionInfo();
      document.getElementById('productsSection').classList.add('hidden');
      document.getElementById('recipesSection').classList.add('hidden');
      this.persistChatState();
    }
  }

  persistChatState(){
    try{
      const key = `chat_messages_${this.userId}`;
    var _mc = document.getElementById('messages');
    const html = (_mc && _mc.innerHTML) || '';
      localStorage.setItem(key, html);
      localStorage.setItem(`chat_session_${this.userId}`, this.sessionId||'');
    }catch(_){}
  }

  restoreChatState(){
    try{
      const key = `chat_messages_${this.userId}`;
      const html = localStorage.getItem(key);
      if (html){
        const messagesContainer = document.getElementById('messages');
        if (messagesContainer){ messagesContainer.innerHTML = html; this.scrollToBottom(); }
      }
      const sid = localStorage.getItem(`chat_session_${this.userId}`);
      if (sid) this.sessionId = sid;
      this.updateSessionInfo();
      const pending = localStorage.getItem(`chat_pending_message_${this.userId}`);
      if (pending){
        this.addMessage(pending, 'user');
        this.sendMessage(pending, true);
        localStorage.removeItem(`chat_pending_message_${this.userId}`);
      }
    }catch(_){ }
  }

  escapeHtml(text){ return (window.UIHelpers && UIHelpers.escapeHtml) ? UIHelpers.escapeHtml(text) : String(text||''); }
  formatPrice(price){ return (window.UIHelpers && UIHelpers.formatPrice) ? UIHelpers.formatPrice(price) : String(price||0); }

  async showCartInChat(){
    if (window.ChatCart) return ChatCart.showCartInChat(this);
    this.addMessage('장바구니 보여주세요','user');
    if (!this.cartState||!this.cartState.items){ if (window.ChatCart) await ChatCart.ensureCartLoaded(this); }
    if (!this.cartState||!this.cartState.items||this.cartState.items.length===0){ this.addMessage('현재 장바구니가 비어있습니다.','bot'); return; }
    let cartMessage='🛒 현재 장바구니 내용:\n\n';
    this.cartState.items.forEach((item,i)=>{
      cartMessage+=`${i+1}. ${item.name}\n`;
      cartMessage+=`   가격: ${this.formatPrice(item.unit_price)}원\n`;
      cartMessage+=`   수량: ${item.qty}개\n`;
      cartMessage+=`   소계: ${this.formatPrice(item.unit_price*item.qty)}원\n\n`;
    });
    cartMessage+=`💰 총 상품금액: ${this.formatPrice(this.cartState.subtotal)}원\n`;
    const discountAmount=(this.cartState.discounts||[]).reduce((acc,d)=>acc+d.amount,0);
    if (discountAmount>0) cartMessage+=`💸 할인금액: -${this.formatPrice(discountAmount)}원\n`;
    cartMessage+=`💳 최종 결제금액: ${this.formatPrice(this.cartState.total)}원`;
    this.addMessage(cartMessage,'bot');
  }


  async fetchAndShowOrderDetails(orderCode) {
    this.showCustomLoading('cs', '주문 내역을 불러오는 중입니다...', 'dots');
    try {
      var _hdr = { 'Content-Type': 'application/json' };
      var _csrf = getCSRFToken && getCSRFToken(); if (_csrf) _hdr['X-CSRFToken'] = _csrf;
      const res = await fetch('/api/orders/details', {
        method: 'POST',
        headers: _hdr,
        body: JSON.stringify({
          order_code: String(orderCode),
          user_id: this.userId
        }),
        credentials: 'include'
      });

      const data = await res.json();

      if (!res.ok || !data || !Array.isArray(data.items) || data.items.length === 0) {
        this.addMessage('해당 주문의 상세 내역을 찾지 못했어요.', 'bot', true);
        return;
      }

      data.isDeliveryInquiry = this.isCurrentlyDeliveryInquiry;
      if (window.ChatCS && typeof ChatCS.renderOrderDetailsBubble === 'function') {
        ChatCS.renderOrderDetailsBubble(this, data);
      }
    } catch (err) {
      console.error('order details error:', err);
      this.addMessage('주문 내역을 불러오던 중 오류가 발생했어요.', 'bot', true);
    } finally {
      this.hideCustomLoading();
    }
  }

  renderOrderDetailsBubble(data) {
    const code = this.escapeHtml(String(data.order_code || ''));
    const date = this.escapeHtml(data.order_date || '');
    const status = this.escapeHtml(data.order_status || '');
    
    const isDelivery = data.isDeliveryInquiry || data.allow_evidence === false || data.category === '배송' || data.list_type === 'delivery';

    const rows = (data.items || []).map((it, idx) => {
      const rawName = it.product || it.name || '';
      const name = this.escapeHtml(rawName);
      const qty = Number(it.quantity || it.qty || 0);
      const price = Number(it.price || it.unit_price || 0);
      const line = price * qty;
      
      const evidenceCell = isDelivery ? '' : `
        <td class="py-1 text-center">
          <button class="evidence-upload-btn px-2 py-1 text-xs border rounded hover:bg-blue-50"
                  data-order="${code}" data-product="${name}">
            <i class="fas fa-camera mr-1"></i>사진 업로드
          </button>
        </td>`;
      
      return `
      <tr class="border-b order-item-row" data-product="${name}" data-qty="${qty}">
        <td class="py-1 pr-3 text-gray-800">${idx + 1}.</td>
        <td class="py-1 pr-3 text-gray-800">${name}</td>
        <td class="py-1 pr-3 text-right">${this.formatPrice(price)}원</td>
        <td class="py-1 pr-3 text-right">${qty}</td>
        <td class="py-1 text-right font-medium">${this.formatPrice(line)}원</td>
        ${evidenceCell}
      </tr>
    `;
    }).join('');

    const subtotal = Number(data.subtotal || data.total_price || 0);
    const total    = Number(data.total || subtotal);
    const discount = Math.max(0, Number(data.discount || 0));
    
    const evidenceHeader = isDelivery ? '' : '<th class="text-center">증빙</th>';
    const evidenceNotice = isDelivery ? '' : '<div class="mt-2 text-xs text-gray-500">* 환불/교환하려는 상품의 <b>사진 업로드</b> 버튼을 눌러 증빙 이미지를 올려주세요.</div>';

    const html = `
    <div class="order-details-bubble" data-order-code="${code}">
      <div class="mb-2 font-semibold text-gray-800">주문 #${code}</div>
      <div class="text-xs text-gray-500 mb-2">${date}${status ? ` · 상태: ${status}` : ''}</div>
      <div class="rounded-lg border overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="text-left py-2 pl-3">#</th>
              <th class="text-left">상품명</th>
              <th class="text-right">단가</th>
              <th class="text-right">수량</th>
              <th class="text-right">금액</th>
              ${evidenceHeader}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${evidenceNotice}
      <div class="mt-2 text-sm">
        <div class="flex justify-between"><span class="text-gray-600">상품 합계</span><span class="font-medium">${this.formatPrice(subtotal)}원</span></div>
        ${discount > 0 ? `<div class="flex justify-between"><span class="text-gray-600">할인</span><span class="font-medium">- ${this.formatPrice(discount)}원</span></div>` : ''}
        <div class="flex justify-between mt-1"><span class="font-semibold">총 결제금액</span><span class="font-bold text-blue-600">${this.formatPrice(total)}원</span></div>
      </div>
    </div>
  `;

    this.addMessage(html, 'bot');
  }

  handleConsultantConnect() {
    if (window.ChatCS && typeof ChatCS.createWaitingMessage === 'function') {
      const waitingMessage = ChatCS.createWaitingMessage();
      this.addMessage(waitingMessage, 'bot');
    }
  }
}

document.addEventListener('DOMContentLoaded', () => { new ChatBot(); });
