// Configuração de ambiente para o frontend Urion Dashboard
// Este arquivo define as URLs da API baseado no ambiente

// Em desenvolvimento (local)
// API_URL = http://localhost:8080
// WS_URL = ws://localhost:8080/ws

// Em produção (virtusinvestimentos.com.br)
// Aponta para o servidor Windows onde o bot roda

export const config = {
  // URL da API REST do backend
  API_URL: import.meta.env.VITE_API_URL || 'http://66.36.233.196:8080',
  
  // URL do WebSocket para dados em tempo real
  WS_URL: import.meta.env.VITE_WS_URL || 'ws://66.36.233.196:8080/ws',
  
  // Nome da aplicação
  APP_NAME: 'Virtus Investimentos',
  
  // Versão
  VERSION: '2.0.0',
  
  // Intervalo de atualização (ms)
  REFRESH_INTERVAL: 5000,
  
  // Timeout de requisições (ms)
  REQUEST_TIMEOUT: 30000,
};

export default config;
