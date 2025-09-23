(function(global){
  'use strict';
  const ChatRecipes = {

    async updateRecipesList(bot, recipePayload){
      const recipesSection = document.getElementById('recipesSection');
      const recipesList = document.getElementById('recipesList');
      const recipesTitle = recipesSection?.querySelector('h3');
      const ingredients = recipePayload?.ingredients;

      let favSet = new Set();
      try {
        const res = await fetch(`/api/recipes/favorites?user_id=${encodeURIComponent(bot.userId)}`, { credentials:'include' });
        const data = await res.json();
        const items = Array.isArray(data?.items) ? data.items : [];
        favSet = new Set(items.map(x => String(x.recipe_url||'').trim()).filter(Boolean));
      } catch (e){ /* no-op */ }

      const hasAnySignal = !!(ingredients && ingredients.length) || !!(recipePayload && (recipePayload.results || recipePayload.selected_recipe || recipePayload.search_query || recipePayload.error));
      if (!hasAnySignal) { if (recipesSection) recipesSection.classList.add('hidden'); return; }

      if (Array.isArray(ingredients) && ingredients.length > 0) {
        bot.productCandidates = ingredients.map(i => ({ name: i.name, origin: i.origin || '원산지 정보 없음', price: i.price || 0, organic: !!i.organic }));
        bot.productPage = 0; bot.productSortBy = 'popular';
        const productsSection = document.getElementById('productsSection');
        productsSection.classList.remove('hidden');
        const productTitle = productsSection.querySelector('h3');
        if (productTitle) productTitle.innerHTML = '<i class="fas fa-shopping-bag mr-2 text-blue-500"></i>추천 재료';
        if (global.ChatProducts) ChatProducts._renderProductPage(bot);
        const productTab = document.getElementById('productTab'); if (productTab) productTab.click();
        return;
      }
      const recipes = recipePayload?.results;
      if (!Array.isArray(recipes) || recipes.length === 0){

        if (recipePayload && (recipePayload.error || recipePayload.search_query)) {
          try { bot.addMessage('죄송합니다. 해당 레시피에서 재료를 검색하는데 실패했습니다. 보다 나은 서비스를 제공하기 위해 최선을 다하겠습니다.', 'bot'); } catch(_) {}
        }
        recipesSection.classList.add('hidden'); return;
      }
      recipesSection.classList.remove('hidden');
      if (recipesTitle) recipesTitle.innerHTML = '<i class="fas fa-utensils mr-2 text-yellow-500"></i>레시피';
      recipesList.innerHTML = '';
      recipes.slice(0,3).forEach((r)=>{
        const title = UIHelpers.escapeHtml(r.title||''); const desc = UIHelpers.escapeHtml(r.description||'');
        const cooking = UIHelpers.escapeHtml(r.cooking_time||''); const servings = UIHelpers.escapeHtml(r.servings||'');
        const url = r.url || '#';
        const card = document.createElement('div');

        card.className = 'recipe-card relative bg-white rounded-lg p-3 border hover:shadow-md transition cursor-pointer mb-2';
        card.innerHTML = `
          <div class="recipe-card-body">
            <h4 class="font-semibold text-gray-800 mb-2">${title}</h4>
            <p class="text-gray-600 mb-2 text-xs">${desc}</p>
            <div class="flex items-center justify-between">
              <div class="recipe-info flex gap-3 text-xs text-gray-500">
                ${cooking ? `<span><i class="fas fa-clock mr-1"></i>${cooking}</span>` : ''}
                ${servings ? `<span><i class="fas fa-user mr-1"></i>${servings}</span>` : ''}
              </div>
              <button class="recipe-ingredients-btn bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-1 rounded text-xs font-medium transition">
                <i class="fas fa-shopping-basket mr-1"></i>재료 추천받기
              </button>
            </div>
          </div>
          <button class="favorite-btn absolute bottom-3 left-3" style="z-index:10" title="즐겨찾기">
            <i class="fas fa-star ${favSet.has(String(url).trim()) ? 'text-yellow-400' : 'text-gray-300'}"></i>
          </button>`;
        card.querySelector('.recipe-ingredients-btn').addEventListener('click',(e)=>{
          e.stopPropagation(); ChatRecipes.requestRecipeIngredients(bot,{ title: r.title, description: r.description, url: r.url });
        });
        card.addEventListener('click',()=>{ if (url && url !== '#') window.open(url, '_blank'); });
        const favBtn=card.querySelector('.favorite-btn');
        favBtn.addEventListener('click',(e)=>{
          e.stopPropagation(); const icon=favBtn.querySelector('i'); const on=icon.classList.contains('text-yellow-400');
          if (on){ icon.classList.remove('text-yellow-400'); icon.classList.add('text-gray-300'); bot.removeFavoriteRecipe({ title:r.title, url:r.url, description:r.description, cooking_time:r.cooking_time, servings:r.servings }); }
          else { icon.classList.remove('text-gray-300'); icon.classList.add('text-yellow-400'); bot.saveFavoriteRecipe({ title:r.title, url:r.url, description:r.description, cooking_time:r.cooking_time, servings:r.servings }); }
        });
        recipesList.appendChild(card);
      });
    },
    async requestRecipeIngredients(bot, recipe){
      const userMessage=`"${recipe.title}" 레시피에 필요한 재료들을 추천해주세요`;
      bot.addMessage(userMessage,'user');
      const requestMessage=`선택된 레시피: "${recipe.title}"
레시피 설명: ${recipe.description||''}
URL: ${recipe.url||''}

이 레시피에 필요한 재료들을 우리 쇼핑몰에서 구매 가능한 상품으로 추천해주세요.`;

      const data = await bot.sendMessage(requestMessage, false);

      if (!data || !data.response) {
        const desc = (recipe.description||'').trim();
        if (desc) bot.addMessage(`레시피 설명: ${desc}`,'bot');
      }
    },
    handleBulkAddToCart(bot){
      const list = document.getElementById('recipesList');
      const checks = list.querySelectorAll('.ingredient-checkbox:checked');
      if (checks.length===0){ alert('담을 재료를 선택해주세요.'); return; }
      const selected = [];
      checks.forEach(cb=>{ selected.push({ name: cb.dataset.productName, price: parseFloat(cb.dataset.productPrice), origin: cb.dataset.productOrigin, organic: cb.dataset.productOrganic === 'true' }); });
      const names = selected.map(p=>p.name).join(', ');
      bot.addMessage(`선택한 재료들을 장바구니에 담아주세요: ${names}`,'user');
      ChatRecipes.sendBulkAddRequest(bot, selected);
    },
    async sendBulkAddRequest(bot, products){
      bot.showCustomLoading('cart','선택한 재료들을 장바구니에 담고 있습니다...','progress');
      try{
        const res = await fetch('/api/cart/bulk-add',{ method:'POST', headers:{ 'Content-Type':'application/json', ...(getCSRFToken()?{'X-CSRFToken':getCSRFToken()}:{}), }, body: JSON.stringify({ user_id:bot.userId, products }), credentials:'include' });
        const data = await res.json(); if (!res.ok) throw new Error(data.detail || '일괄 담기 실패');
        const successCount = data.added_count || products.length; bot.addMessage(`${successCount}개의 재료가 장바구니에 담겼습니다!`,'bot'); if (data.cart) bot.updateCart(data.cart, true);
        const list = document.getElementById('recipesList'); list.querySelectorAll('.ingredient-checkbox').forEach(cb=>cb.checked=false); const all = list.querySelector('#select-all-ingredients'); if (all) all.checked=false;
      }catch(err){ console.error('Bulk add error:', err); bot.addMessage('선택한 재료를 담는 중 오류가 발생했습니다.','bot',true);
      }finally{ bot.hideCustomLoading(); }
    },
  };
  global.ChatRecipes = ChatRecipes;
})(window);
