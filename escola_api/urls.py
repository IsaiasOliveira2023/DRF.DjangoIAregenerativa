# SEU ARQUIVO PRINCIPAL: escola_api/urls.py (CÓDIGO FINAL E CORRETO)

from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
# Garante que todas as 3 ViewSets são importadas
from materias.views import MateriaViewSet, ProfessorViewSet, ReservaLaboratorioViewSet 

# Criação e Registro do Router
router = routers.DefaultRouter()
# 1. Registro de Matérias
router.register(r'materias', MateriaViewSet) 
# 2. Registro de Professores
router.register(r'professores', ProfessorViewSet) 
# 3. Registro de Reservas
router.register(r'reservas', ReservaLaboratorioViewSet) 

urlpatterns = [
    path('admin/', admin.site.urls),
    # Esta linha final usa o router completo para o prefixo /api/
    path('api/', include(router.urls)), 
]