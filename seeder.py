# seeder.py
import os
import sys
from datetime import date, time, timedelta, datetime

# === AJUSTA ESTO SI TU SETTINGS CAMBIA ===
DJANGO_SETTINGS_MODULE = os.environ.get("DJANGO_SETTINGS_MODULE", "horarios.settings")

def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)
    sys.path.append(os.getcwd())
    import django
    django.setup()

def tadd(t: time, minutes: int) -> time:
    dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return dt.time()

def main():
    setup_django()
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone

    # users
    from users.models import UserProfile, UserRole, Docente, Estudiante

    # academics
    from academics.models import (
        Carrera, Asignatura, Periodo, Turno, Grupo, Preinscripcion,
        TipoAmbiente as TipoAmbienteAcad
    )

    # facilities
    from facilities.models import Edificio, TipoAmbiente, Ambiente

    # scheduling
    from scheduling.models import Calendario, Bloque, DisponibilidadDocente, Clase, DiaSemana

    User = get_user_model()

    print(f"Usando settings: {DJANGO_SETTINGS_MODULE}")
    with transaction.atomic():
        # --- Usuarios base ---
        admin, _ = User.objects.get_or_create(username="admin", defaults=dict(email="admin@uni.edu"))
        if not admin.has_usable_password():
            admin.set_password("Secreta123"); admin.is_staff=True; admin.is_superuser=True; admin.save()

        def create_user(u, email, role, nombre=None, password="Secreta123"):
            user, created = User.objects.get_or_create(username=u, defaults=dict(email=email))
            if created or not user.has_usable_password():
                user.set_password(password)
                user.save()
            prof, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": role})
            if prof.role != role:
                prof.role = role; prof.save(update_fields=["role"])
            return user

        # Jefatura / Autoridades
        u_jefe = create_user("jefe", "jefe@uni.edu", UserRole.JEFE_CARRERA)
        u_vicer = create_user("vicer", "vicer@uni.edu", UserRole.VICERRECTORADO)
        u_rector = create_user("rector", "rector@uni.edu", UserRole.RECTOR)

        # Docentes
        u_d1 = create_user("doc1", "doc1@uni.edu", UserRole.DOCENTE)
        u_d2 = create_user("doc2", "doc2@uni.edu", UserRole.DOCENTE)
        u_d3 = create_user("doc3", "doc3@uni.edu", UserRole.DOCENTE)

        d1, _ = Docente.objects.update_or_create(
            user=u_d1,
            defaults=dict(
                nombre_completo="Dra. Ana Quiroga",
                especialidad="Química General",
                carga_min_semanal=6,
                carga_max_semanal=16,
                activo=True,
            ),
        )
        d2, _ = Docente.objects.update_or_create(
            user=u_d2,
            defaults=dict(
                nombre_completo="MSc. Bruno Pérez",
                especialidad="Bioquímica",
                carga_min_semanal=6,
                carga_max_semanal=16,
                activo=True,
            ),
        )
        d3, _ = Docente.objects.update_or_create(
            user=u_d3,
            defaults=dict(
                nombre_completo="Ing. Carla Ríos",
                especialidad="Laboratorio",
                carga_min_semanal=4,
                carga_max_semanal=12,
                activo=True,
            ),
        )

        # Estudiantes (mínimo para HU010/inscripciones)
        estudiantes = []
        for i in range(1, 41):  # 40 est.
            u = create_user(f"est{i}", f"est{i}@uni.edu", UserRole.ESTUDIANTE)
            e, _ = Estudiante.objects.get_or_create(user=u, defaults={"nombre_completo": f"Estudiante {i}", "matricula": f"MAT{i:04d}"})
            estudiantes.append(e)

        # --- Academics ---
        bioq, _ = Carrera.objects.get_or_create(sigla="BIOQ", defaults={"nombre": "Bioquímica", "jefe": u_jefe})

        # TipoAmbiente para compatibilidad en Asignatura (usamos el de academics para referencia)
        ta_aula_acad, _ = TipoAmbienteAcad.objects.get_or_create(nombre="Aula", defaults={"descripcion": "Aula teórica"})
        ta_lab_acad, _ = TipoAmbienteAcad.objects.get_or_create(nombre="Laboratorio", defaults={"descripcion": "Laboratorio práctico"})

        # Asignaturas con horas/semana
        bio101, _ = Asignatura.objects.get_or_create(
            carrera=bioq, codigo="BIO101",
            defaults=dict(
                nombre="Química General",
                horas_teoria_semana=3, horas_practica_semana=2,
                tipo_ambiente_teoria=ta_aula_acad, tipo_ambiente_practica=ta_lab_acad,
            ),
        )
        bio201, _ = Asignatura.objects.get_or_create(
            carrera=bioq, codigo="BIO201",
            defaults=dict(
                nombre="Bioquímica I",
                horas_teoria_semana=2, horas_practica_semana=2,
                tipo_ambiente_teoria=ta_aula_acad, tipo_ambiente_practica=ta_lab_acad,
            ),
        )

        # Periodo y Turnos
        per, _ = Periodo.objects.get_or_create(
            gestion=2025, numero=2,
            defaults=dict(fecha_inicio=date(2025, 8, 1), fecha_fin=date(2025, 12, 1))
        )
        t_man, _ = Turno.objects.get_or_create(nombre="Mañana")
        t_tar, _ = Turno.objects.get_or_create(nombre="Tarde")
        t_noc, _ = Turno.objects.get_or_create(nombre="Noche")

        # --- Facilities ---
        ed_a, _ = Edificio.objects.get_or_create(codigo="ED-A", defaults={"nombre": "Bloque A", "ubicacion": "Campus Norte"})
        ed_b, _ = Edificio.objects.get_or_create(codigo="ED-B", defaults={"nombre": "Bloque B", "ubicacion": "Campus Norte"})

        ta_aula, _ = TipoAmbiente.objects.get_or_create(nombre="Aula", defaults={"descripcion": "Aula teórica"})
        ta_lab, _ = TipoAmbiente.objects.get_or_create(nombre="Laboratorio", defaults={"descripcion": "Laboratorio práctico"})

        a_101, _ = Ambiente.objects.get_or_create(edificio=ed_a, tipo_ambiente=ta_aula, codigo="A-101", defaults={"nombre": "Aula 101", "capacidad": 50})
        a_102, _ = Ambiente.objects.get_or_create(edificio=ed_a, tipo_ambiente=ta_aula, codigo="A-102", defaults={"nombre": "Aula 102", "capacidad": 30})
        b_lab1, _ = Ambiente.objects.get_or_create(edificio=ed_b, tipo_ambiente=ta_lab, codigo="LAB-1", defaults={"nombre": "Lab 1", "capacidad": 25})
        b_lab2, _ = Ambiente.objects.get_or_create(edificio=ed_b, tipo_ambiente=ta_lab, codigo="LAB-2", defaults={"nombre": "Lab 2", "capacidad": 40})

        # --- Calendario y bloques (45') ---
        cal, _ = Calendario.objects.get_or_create(periodo=per, nombre="Calendario 2025-2", defaults={"duracion_bloque_min": 45})

        # Generamos 8 bloques de 45' desde 08:00
        start = time(8, 0)
        for i in range(1, 9):
            ini = tadd(start, (i-1)*45)
            fin = tadd(ini, 45)
            Bloque.objects.get_or_create(
                calendario=cal, orden=i,
                defaults={"hora_inicio": ini, "hora_fin": fin, "duracion_min": 45}
            )

        # --- Disponibilidades por docente ---
        # d1: Lunes y Miércoles bloques 1-4
        for day in (DiaSemana.LUNES, DiaSemana.MIERCOLES):
            b1 = Bloque.objects.get(calendario=cal, orden=1)
            DisponibilidadDocente.objects.get_or_create(docente=d1, calendario=cal, day_of_week=day, bloque_inicio=b1, defaults={"bloques_duracion": 4, "preferencia": 1})
        # d2: Martes y Jueves bloques 3-6
        for day in (DiaSemana.MARTES, DiaSemana.JUEVES):
            b3 = Bloque.objects.get(calendario=cal, orden=3)
            DisponibilidadDocente.objects.get_or_create(docente=d2, calendario=cal, day_of_week=day, bloque_inicio=b3, defaults={"bloques_duracion": 4, "preferencia": 1})
        # d3: Viernes bloques 1-6
        b1 = Bloque.objects.get(calendario=cal, orden=1)
        DisponibilidadDocente.objects.get_or_create(docente=d3, calendario=cal, day_of_week=DiaSemana.VIERNES, bloque_inicio=b1, defaults={"bloques_duracion": 6, "preferencia": 0})

        # --- Preinscripciones (para HU010 sugerir 1/25) ---
        # 35 Mañana BIO101 + 25 Tarde BIO101 => sugerirá 2 grupos por turno
        created_pre = 0
        for i, est in enumerate(estudiantes[:35], start=1):
            obj, created = Preinscripcion.objects.get_or_create(periodo=per, asignatura=bio101, turno=t_man, estudiante=est)
            if created: created_pre += 1
        for i, est in enumerate(estudiantes[35:60], start=1):
            obj, created = Preinscripcion.objects.get_or_create(periodo=per, asignatura=bio101, turno=t_tar, estudiante=est)
            if created: created_pre += 1

        # --- Grupos (algunos con docente para probar persistir/preview) ---
        g_a1, _ = Grupo.objects.get_or_create(asignatura=bio101, periodo=per, turno=t_man, codigo="A1", defaults={"docente": d1, "capacidad": 35, "estado": "borrador"})
        g_a2, _ = Grupo.objects.get_or_create(asignatura=bio101, periodo=per, turno=t_man, codigo="A2", defaults={"docente": d2, "capacidad": 35, "estado": "borrador"})
        g_b1, _ = Grupo.objects.get_or_create(asignatura=bio101, periodo=per, turno=t_tar, codigo="B1", defaults={"docente": d2, "capacidad": 30, "estado": "borrador"})
        g_b2, _ = Grupo.objects.get_or_create(asignatura=bio101, periodo=per, turno=t_tar, codigo="B2", defaults={"docente": d3, "capacidad": 30, "estado": "borrador"})

        # Inscribir algunos estudiantes a A1/B1 para probar reportes/horario
        for est in estudiantes[:20]:
            _ = est  # noqa
            try:
                from academics.models import Inscripcion
                Inscripcion.objects.get_or_create(grupo=g_a1, estudiante=est)
            except Exception:
                pass
        for est in estudiantes[20:35]:
            try:
                from academics.models import Inscripcion
                Inscripcion.objects.get_or_create(grupo=g_b1, estudiante=est)
            except Exception:
                pass

        # --- Clases de prueba (incluye un choque para HU012) ---
        b1 = Bloque.objects.get(calendario=cal, orden=1)
        b3 = Bloque.objects.get(calendario=cal, orden=3)

        # Clase A1 Teoría Lunes bloques 1-2 en Aula 101 (docente d1)
        c1, _ = Clase.objects.get_or_create(
            grupo=g_a1, tipo="T", day_of_week=DiaSemana.LUNES,
            bloque_inicio=b1, bloques_duracion=2,
            docente=d1, ambiente=a_101,
            defaults={"estado": "confirmado", "creado_en": timezone.now(), "confirmado_en": timezone.now()},
        )
        # Clase A2 Teoría Lunes bloques 2-3 en MISMO AULA (choque en AMBIENTE) y MISMO DOCENTE? (ponemos d1 para choque docente)
        c2, created_c2 = Clase.objects.get_or_create(
            grupo=g_a2, tipo="T", day_of_week=DiaSemana.LUNES,
            bloque_inicio=b3, bloques_duracion=2,  # b3 (orden 3) se solapa con c1? c1 ocupa 1-2, c2 3-4 => sin solape con c1 por docente
            docente=d1, ambiente=a_101,
            defaults={"estado": "propuesto", "creado_en": timezone.now()},
        )
        # Para garantizar un conflicto, añadimos otra clase que se solape con c1 en docente:
        # A1 Práctica Lunes bloques 2-3 con mismo docente (d1) en Lab 2 => DOCENTE en conflicto con c1
        c3, _ = Clase.objects.get_or_create(
            grupo=g_a1, tipo="P", day_of_week=DiaSemana.LUNES,
            bloque_inicio=Bloque.objects.get(calendario=cal, orden=2), bloques_duracion=2,
            docente=d1, ambiente=b_lab2,
            defaults={"estado": "propuesto", "creado_en": timezone.now()},
        )

        # Clases sin conflicto (B1 Martes teoria/práctica con d2 y ambientes correctos)
        Clase.objects.get_or_create(
            grupo=g_b1, tipo="T", day_of_week=DiaSemana.MARTES,
            bloque_inicio=b3, bloques_duracion=2,
            docente=d2, ambiente=a_102,
            defaults={"estado": "confirmado", "creado_en": timezone.now(), "confirmado_en": timezone.now()},
        )
        Clase.objects.get_or_create(
            grupo=g_b1, tipo="P", day_of_week=DiaSemana.JUEVES,
            bloque_inicio=b1, bloques_duracion=2,
            docente=d2, ambiente=b_lab1,
            defaults={"estado": "propuesto", "creado_en": timezone.now()},
        )

    # --- Resumen / comandos útiles ---
    print("\n=== SEED OK ===")
    print("Usuarios creados:")
    print("  admin / Secreta123 (superuser)")
    print("  jefe  / Secreta123 (JEFE_CARRERA)")
    print("  vicer / Secreta123 (VICERRECTORADO)")
    print("  rector/ Secreta123 (RECTOR)")
    print("  doc1  / Secreta123 (DOCENTE) Ana Quiroga")
    print("  doc2  / Secreta123 (DOCENTE) Bruno Pérez")
    print("  doc3  / Secreta123 (DOCENTE) Carla Ríos")
    print("  est1..est40 / Secreta123 (ESTUDIANTE)")
    print("\nDatos clave:")
    print("  Carrera: BIOQ")
    print("  Asignaturas: BIO101 (3T,2P), BIO201 (2T,2P)")
    print("  Periodo: 2025/2, Calendario: 8 bloques de 45’ desde 08:00")
    print("  Turnos: Mañana/Tarde/Noche")
    print("  Ambientes: A-101(50), A-102(30), LAB-1(25), LAB-2(40)")
    print("  Grupos: A1/A2 (Mañana), B1/B2 (Tarde)")
    print("  Disponibilidades: d1 (Lun/Mie 1-4), d2 (Mar/Jue 3-6), d3 (Vie 1-6)")
    print("  Clases de prueba: c1/c2/c3 (incluye conflictos DOCENTE y AMBIENTE)")

    print("\nPrueba rápida de endpoints (JWT requerido):")
    print("  - Proponer docentes:     POST /api/scheduling/asignacion/docentes/proponer/ {periodo:1, calendario:1, persistir:false}")
    print("  - Proponer clases:       POST /api/scheduling/asignacion/clases/proponer/ {periodo:1, calendario:1, persistir:false}")
    print("  - Detectar conflictos:   POST /api/scheduling/conflictos/detectar/ {periodo:1, persistir:true}")
    print("  - Asignar aulas:         POST /api/scheduling/aulas/asignar/ {periodo:1, calendario:1}")
    print("  - Grid semanal:          POST /api/scheduling/grid/semana/ {periodo:1, calendario:1}")
    print("  - Cargas docentes:       GET  /api/scheduling/cargas/docentes/?periodo=1&calendario=1")
    print("\n¡Listo para probar HU011–HU019!")

if __name__ == "__main__":
    main()
