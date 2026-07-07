# quimera/agentes/refinador_v3/config_refinador.py

"""
Configurações específicas para o AgenteRefinadorV3.
Isso isola os parâmetros do refinador do config.py global do Quimera.
"""

# Limiar de score (0.0 a 1.0) que um patch deve atingir para ser considerado "bom o suficiente"
# e parar o ciclo de refinamento. É ideal que seja mais alto que o MIN_SCORE_PARA_APLICACAO do Quimera.
LIMIAR_ACEITE = 0.92

# Número máximo de ciclos de refinamento que o agente executará em um único patch
# antes de desistir e retornar a melhor versão encontrada.
MAX_ITERACOES = 5

# Parâmetro para o algoritmo epsilon-greedy do BanditController.
# Representa a probabilidade (de 0.0 a 1.0) de escolher uma heurística de mutação
# aleatória (exploração) em vez de escolher a melhor conhecida (explotação).
# Um valor de 0.2 significa 20% de chance de explorar.
EPSILON = 0.2