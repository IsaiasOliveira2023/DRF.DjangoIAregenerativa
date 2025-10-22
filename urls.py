# Seu Projeto Django: escola_api/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
# Linha CRÍTICA (deve ter as 3 ViewSets):
from materias.views import MateriaViewSet, ProfessorViewSet, ReservaLaboratorioViewSet 

# ... o restante do código deve estar como abaixo ...
router = routers.DefaultRouter()
router.register(r'materias', MateriaViewSet) 
router.register(r'professores', ProfessorViewSet) 
router.register(r'reservas', ReservaLaboratorioViewSet) 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)), 
]