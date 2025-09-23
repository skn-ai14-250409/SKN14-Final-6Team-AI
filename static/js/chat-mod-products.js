(function(global){
  'use strict';
  const ChatProducts = {

    sortProducts(products, sortBy){
      if (!Array.isArray(products) || products.length === 0) return products || [];
      const sortedProducts = products.slice();
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
    },
    createSortSelectBox(bot, currentSortBy, onChangeCallback, elementId){
      const sortOptions = [
        { value: 'popular', label: '인기순' },
        { value: 'price_low', label: '가격 낮은순' },
        { value: 'price_high', label: '가격 높은순' },
      ];

      const selectHtml =
        '<div class="flex items-center justify-between mb-3">'
        +   '<span class="text-sm font-medium text-gray-700">정렬 기준</span>'
        +   `<select id="${elementId}" class="sort-select text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:border-green-500 focus:outline-none">`
        +   sortOptions.map((option) =>
              `<option value="${option.value}" ${currentSortBy === option.value ? 'selected' : ''}>${option.label}</option>`
            ).join('')
        +   '</select>'
        + '</div>';

      return {
        html: selectHtml,
        bindEvent: (container) => {
          const selectElement = container.querySelector(`#${elementId}`);
          if (selectElement) {
            selectElement.addEventListener('change', (e) => {
              onChangeCallback(e.target.value);
            });
          }
        }
      };
    },
    _renderPaginatedList(bot, config){
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

      if (!listElement || !Array.isArray(dataArray)) return;
      listElement.innerHTML = '';

      if (sortConfig) {
        const sortContainer = document.createElement('div');
        sortContainer.className = 'sort-container mb-0 p-1 bg-gray-50 rounded-lg';
        sortContainer.innerHTML = sortConfig.html;
        listElement.appendChild(sortContainer);
        if (sortConfig.bindEvent) sortConfig.bindEvent(sortContainer);
      }

      const totalItems = dataArray.length;
      const totalPages = Math.ceil(totalItems / itemsPerPage) || 1;
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
        if (validPage === 0) prevBtn.disabled = true;
        prevBtn.addEventListener('click', () => onPageChange(validPage - 1));

        const pageInfo = document.createElement('span');
        pageInfo.className = 'text-xs font-medium text-gray-600 px-2';
        pageInfo.textContent = `${validPage + 1} / ${totalPages}`;

        const nextBtn = document.createElement('button');
        nextBtn.innerHTML = '<i class="fas fa-chevron-right"></i>';
        nextBtn.className = 'pagination-btn px-2 py-1 text-xs border rounded hover:bg-gray-100 disabled:opacity-50';
        if (validPage === totalPages - 1) nextBtn.disabled = true;
        nextBtn.addEventListener('click', () => onPageChange(validPage + 1));

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

        if (Array.isArray(bulkActionConfig.events)) {
          bulkActionConfig.events.forEach((event) => {
            const element = bulkContainer.querySelector(event.selector);
            if (element) element.addEventListener(event.type, event.handler);
          });
        }
      }
    },
    updateProductsList(bot, products){
      const section=document.getElementById('productsSection');
      if (products) { bot.productCandidates = products; bot.productPage = 0; bot.productSortBy = 'popular'; }
      if (!bot.productCandidates || bot.productCandidates.length === 0) { section.classList.add('hidden'); return; }
      section.classList.remove('hidden');
      ChatProducts._renderProductPage(bot);
    },
    handleProductSortChange(bot, newSortBy){ bot.productSortBy = newSortBy; bot.productPage = 0; ChatProducts._renderProductPage(bot); },
    _renderProductPage(bot){
      const sortedProducts = ChatProducts.sortProducts(bot.productCandidates, bot.productSortBy);
      const sortConfig = ChatProducts.createSortSelectBox(bot, bot.productSortBy, function(v){ ChatProducts.handleProductSortChange(bot,v); }, 'productSortSelect');
      ChatProducts._renderPaginatedList(bot, {
        listElement: document.getElementById('productsList'),
        dataArray: sortedProducts,
        currentPage: bot.productPage,
        itemsPerPage: bot.PRODUCTS_PER_PAGE,
        renderItemCallback: function(product){
          const card = document.createElement('div');
          card.className = 'product-card';

          var html = ''
            + '<div class="product-info">'
            +   '<h4 class="font-medium text-sm text-gray-800">'+UIHelpers.escapeHtml(product.name)+'</h4>'
            +   '<p class="text-xs text-gray-500 mt-1">'+UIHelpers.escapeHtml(product.origin || '원산지 정보 없음')+'</p>'
            +   '<div class="flex items-center mt-1">'
            +     '<p class="text-green-600 font-bold text-sm">'+UIHelpers.formatPrice(product.price)+'원</p>'
            +     (product.organic ? '<span class="ml-2 px-1 py-0.5 bg-green-100 text-green-700 text-xs rounded">유기농</span>' : '')
            +   '</div>'
            + '</div>'
            + '<button class="add-to-cart bg-green-100 text-green-600 px-3 py-1 rounded text-xs hover:bg-green-200 ml-auto" data-product-name="'+UIHelpers.escapeHtml(product.name)+'">담기</button>';
          card.innerHTML = html;
          card.querySelector('.add-to-cart').addEventListener('click', async function(e){
            e.stopPropagation();
            try {
              if (!bot.cartState || !bot.cartState.items) {
                if (global.ChatCart) await ChatCart.ensureCartLoaded(bot);
              }
              if (!bot.cartState) bot.cartState = { items: [], discounts: [], subtotal: 0, total: 0 };
              if (!Array.isArray(bot.cartState.items)) bot.cartState.items = [];
              var idx = bot.cartState.items.findIndex(function(i){ return i.name === product.name; });
              if (idx >= 0) bot.cartState.items[idx].qty += 1; else bot.cartState.items.push({ name: product.name, qty: 1, unit_price: product.price });
              if (global.ChatCart) ChatCart.optimisticRecalculateAndRedrawCart(bot);
            } catch(_){ }

            try {
              if (typeof bot.showCustomLoading === 'function') bot.showCustomLoading('cart','장바구니에 담는 중입니다...','progress');
              var headers = { 'Content-Type':'application/json' };
              var csrf = getCSRFToken && getCSRFToken(); if (csrf) headers['X-CSRFToken'] = csrf;
              var res = await fetch('/api/cart/bulk-add', {
                method:'POST', headers: headers, credentials:'include',
                body: JSON.stringify({ user_id: bot.userId, products: [{ name: product.name, price: product.price||0, origin: product.origin||'', organic: !!product.organic }] })
              });
              var data = await res.json();
              if (data && data.cart && typeof bot.updateCart === 'function') bot.updateCart(data.cart, true);

              try { bot.addMessage(UIHelpers.escapeHtml(product.name)+'을 장바구니에 담았습니다.', 'bot'); } catch(_) {}
            } catch(err){ console.error('add-to-cart error', err); }
            finally { if (typeof bot.hideCustomLoading === 'function') bot.hideCustomLoading(); }
          });
          return card;
        },
        onPageChange: function(p){ bot.productPage=p; ChatProducts._renderProductPage(bot); },
        sortConfig: sortConfig
      });
    }
  };
  global.ChatProducts = ChatProducts;
})(window);
