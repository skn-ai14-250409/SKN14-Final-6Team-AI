"""
채팅 뷰
"""
from django.shortcuts import render
from django.views.generic import TemplateView


class LandingView(TemplateView):
    """랜딩 페이지"""
    template_name = 'landing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Qook - 신선한 하루의 시작'
        return context


class ChatView(TemplateView):
    """챗봇 페이지"""
    template_name = 'chat.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Qook 챗봇 - 신선한 대화'
        return context