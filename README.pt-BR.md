<!-- SPDX-License-Identifier: MIT -->

# RustChain

**Uma plataforma blockchain descentralizada para mineração distribuída e mercado de trabalho**

[English](README.md) | **Português (Brasil)**

## Visão Geral

RustChain é um sistema blockchain descentralizado projetado para criar um mercado de trabalho peer-to-peer onde usuários podem postar trabalhos, minerar blocos e ganhar tokens RTC (RustChain Token). O sistema combina mineração de prova de trabalho (PoW) com um marketplace integrado para tarefas computacionais.

## Características Principais

- **Mineração Distribuída**: Sistema de prova de trabalho com recompensas automáticas
- **Mercado de Trabalho**: Plataforma para postar e aceitar trabalhos pagos em RTC
- **Arquitetura Peer-to-Peer**: Comunicação descentralizada entre nós
- **Sistema de Carteira**: Gerenciamento integrado de tokens RTC
- **API RESTful**: Interface completa para interação com a blockchain
- **Consenso Automático**: Sincronização e validação de blockchain entre nós

## Instalação Rápida

### Pré-requisitos

- Python 3.8+
- pip
- git

### Configuração

1. **Clone o repositório**
   ```bash
   git clone https://github.com/Scottcjn/Rustchain.git
   cd Rustchain
   ```

2. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

3. **Inicie um nó**
   ```bash
   python node/rustchain_v2_integrated_v2.2.1_rip200.py
   ```

O nó será iniciado em `http://localhost:5000` por padrão.

## Uso

### Iniciando a Mineração

```bash
# Inicie a mineração em um nó
curl -X POST http://localhost:5000/start_mining

# Pare a mineração
curl -X POST http://localhost:5000/stop_mining
```

### Gerenciamento de Carteira

```bash
# Consulte o saldo
curl http://localhost:5000/balance

# Liste todas as carteiras
curl http://localhost:5000/wallets
```

### Marketplace de Trabalhos

```bash
# Poste um trabalho
curl -X POST http://localhost:5000/post_job \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Análise de Dados",
    "description": "Processar dataset CSV",
    "payment": 10.0,
    "miner_id": "sua-carteira-id"
  }'

# Liste trabalhos disponíveis
curl http://localhost:5000/jobs
```

### Conectando Múltiplos Nós

```bash
# Conecte nós para formar uma rede
curl -X POST http://localhost:5000/connect_node \
  -H "Content-Type: application/json" \
  -d '{"node": "http://localhost:5001"}'
```

## Arquitetura

### Componentes Principais

- **Blockchain Core**: Gerenciamento de blocos, transações e consenso
- **Sistema de Mineração**: Algoritmo de prova de trabalho com dificuldade ajustável
- **P2P Network**: Comunicação e sincronização entre nós
- **Job Marketplace**: Sistema de escrow para trabalhos pagos
- **Wallet System**: Gerenciamento de chaves e saldos
- **REST API**: Interface HTTP para todas as operações

### Estrutura de Dados

```python
# Estrutura do Bloco
{
    "index": 1,
    "timestamp": "2024-01-01T00:00:00",
    "transactions": [...],
    "previous_hash": "0x...",
    "nonce": 12345,
    "hash": "0x..."
}

# Estrutura da Transação
{
    "from": "wallet_id",
    "to": "wallet_id",
    "amount": 10.0,
    "fee": 0.1,
    "timestamp": "2024-01-01T00:00:00"
}
```

## API Endpoints

### Blockchain

- `GET /chain` - Obter blockchain completa
- `GET /mine` - Minerar um novo bloco
- `POST /transactions/new` - Criar nova transação
- `GET /nodes/resolve` - Resolver conflitos de consenso

### Mineração

- `POST /start_mining` - Iniciar mineração automática
- `POST /stop_mining` - Parar mineração
- `GET /mining_status` - Status da mineração

### Trabalhos

- `POST /post_job` - Postar novo trabalho
- `GET /jobs` - Listar trabalhos disponíveis
- `POST /accept_job` - Aceitar um trabalho
- `POST /complete_job` - Marcar trabalho como concluído

### Rede

- `POST /connect_node` - Conectar a um nó
- `GET /nodes` - Listar nós conectados
- `POST /sync` - Sincronizar com a rede

## Desenvolvimento

### Estrutura do Projeto

```
Rustchain/
├── node/                    # Nó principal da blockchain
├── agent-economy-demo/      # Sistema de agentes autônomos
├── bounties/               # Sistema de recompensas
├── tools/                  # Utilitários e ferramentas
├── tests/                  # Testes automatizados
└── docs/                   # Documentação
```

### Executando Testes

```bash
# Execute todos os testes
python -m pytest

# Teste específico
python -m pytest tests/test_blockchain.py
```

### Configuração de Desenvolvimento

```bash
# Instale dependências de desenvolvimento
pip install -r requirements-dev.txt

# Execute linting
ruff check .

# Execute verificação de tipos
mypy .
```

## Configuração de Rede

### Configuração de Múltiplos Nós

1. **Inicie o primeiro nó (porta 5000)**
   ```bash
   python node/rustchain_v2_integrated_v2.2.1_rip200.py
   ```

2. **Inicie nós adicionais**
   ```bash
   PORT=5001 python node/rustchain_v2_integrated_v2.2.1_rip200.py
   PORT=5002 python node/rustchain_v2_integrated_v2.2.1_rip200.py
   ```

3. **Conecte os nós**
   ```bash
   curl -X POST http://localhost:5001/connect_node \
     -H "Content-Type: application/json" \
     -d '{"node": "http://localhost:5000"}'
   ```

## Economia do Token

### RTC (RustChain Token)

- **Recompensa de Mineração**: 10 RTC por bloco
- **Taxa de Transação**: 0.1 RTC (padrão)
- **Pagamento de Trabalhos**: Valores personalizados
- **Sistema de Escrow**: Proteção automática para trabalhos

### Métricas Econômicas

```bash
# Consulte estatísticas do mercado
curl http://localhost:5000/marketplace_stats

# Consulte métricas da blockchain
curl http://localhost:5000/stats
```

## Segurança

### Características de Segurança

- **Validação Criptográfica**: SHA-256 para hashing de blocos
- **Consenso Distribuído**: Resolução automática de conflitos
- **Sistema de Escrow**: Proteção de fundos para trabalhos
- **Validação de Transações**: Verificação de saldo e assinaturas

### Melhores Práticas

- Mantenha as chaves da carteira seguras
- Use HTTPS em produção
- Configure firewalls apropriados
- Monitore regularmente os logs do nó

## Contribuindo

### Como Contribuir

1. Faça fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Crie um Pull Request

### Diretrizes de Desenvolvimento

- Siga o padrão de código Python (PEP 8)
- Adicione testes para novas funcionalidades
- Atualize a documentação conforme necessário
- Use mensagens de commit descritivas

## Roadmap

### Versão Atual (v2.2.1)

- ✅ Blockchain básica com PoW
- ✅ Marketplace de trabalhos
- ✅ API RESTful
- ✅ Mineração automática
- ✅ Sincronização P2P

### Próximas Versões

- 🔄 Interface web melhorada
- 🔄 Sistema de reputação
- 🔄 Contratos inteligentes básicos
- 🔄 Mobile wallet
- 🔄 Optimizações de performance

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## Suporte

### Comunidade

- **GitHub Issues**: [Reportar bugs ou solicitar features](https://github.com/Scottcjn/Rustchain/issues)
- **Discussions**: [Discussões da comunidade](https://github.com/Scottcjn/Rustchain/discussions)

### Links Úteis

- [Documentação da API](docs/api.md)
- [Guia de Desenvolvimento](docs/development.md)
- [FAQ](docs/faq.md)
- [Changelog](CHANGELOG.md)

---

**RustChain** - Construindo o futuro do trabalho descentralizado, um bloco de cada vez.
