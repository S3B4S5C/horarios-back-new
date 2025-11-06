from io import BytesIO
from typing import List
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from scheduling.models import Clase, Bloque
from users.permissions import IsTeacherOrManager
from users.models import Docente  # <— para obtener el nombre si viene ?docente=

DOW_LABEL = {1:"Lunes",2:"Martes",3:"Miércoles",4:"Jueves",5:"Viernes",6:"Sábado",7:"Domingo"}

def _parse_dias(qsparam: str | None) -> List[int]:
    if not qsparam:
        return [1,2,3,4,5]
    out=[]
    for p in qsparam.split(","):
        try:
            d=int(p.strip())
            if 1<=d<=7: out.append(d)
        except ValueError:
            pass
    return out or [1,2,3,4,5]

def _wrap_text(c: canvas.Canvas, text: str, max_w: float, max_lines: int, base_font="Helvetica", base_size=8):
    words=text.split()
    for size in range(base_size,6,-1):
        lines,cur=[], ""
        for w in words:
            cand=w if not cur else cur+" "+w
            if stringWidth(cand, base_font, size) <= max_w:
                cur=cand
            else:
                if cur: lines.append(cur)
                cur=w
            if len(lines)>=max_lines: break
        if cur and len(lines)<max_lines: lines.append(cur)
        if len(lines)<=max_lines:
            return lines[:max_lines], size
    return [text[: max(0,int(max_w/(stringWidth("M","Helvetica",6) or 1)))]], 6

@extend_schema(
    tags=["export"],
    parameters=[],
    responses={(200, "application/pdf"): OpenApiTypes.BINARY},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTeacherOrManager])
def export_pdf_view(request):
    """
    Exporta horario semanal en PDF como grilla (días × bloques).
    Filtros: ?periodo=&calendario=&docente=&grupo=&ambiente=&dias=1,2,3,4,5
    """
    try:
        periodo_id = int(request.query_params.get("periodo"))
        calendario_id = int(request.query_params.get("calendario"))
    except (TypeError, ValueError):
        return HttpResponse("periodo y calendario son requeridos", status=400)

    dias = _parse_dias(request.query_params.get("dias"))

    qs = (
        Clase.objects.select_related("grupo__asignatura","docente","ambiente","bloque_inicio")
        .filter(grupo__periodo_id=periodo_id, bloque_inicio__calendario_id=calendario_id)
        .exclude(estado="cancelado")
        .filter(day_of_week__in=dias)
        .order_by("day_of_week","bloque_inicio__orden","grupo__asignatura__codigo")
    )
    # filtros adicionales
    for p in ("docente","grupo","ambiente"):
        val = request.query_params.get(p)
        if val: qs = qs.filter(**{f"{p}_id": val})

    bloques = list(Bloque.objects.filter(calendario_id=calendario_id).order_by("orden"))
    if not bloques:
        return HttpResponse("No hay bloques para el calendario dado.", status=400)
    bloque_index = {b.orden: i for i,b in enumerate(bloques)}

    # ======== ENCABEZADO: construir subtítulo con NOMBRE de docente ========
    docente_nombre = None
    docente_param = request.query_params.get("docente")
    if docente_param:
        try:
            docente_obj = Docente.objects.only("nombre_completo").get(pk=int(docente_param))
            docente_nombre = docente_obj.nombre_completo
        except (Docente.DoesNotExist, ValueError):
            docente_nombre = None
    elif request.query_params.get("grupo"):
        # Si se filtró por grupo, el queryset debe tener un único docente
        nombres = list(qs.values_list("docente__nombre_completo", flat=True).distinct())
        nombres = [n for n in nombres if n]
        if len(nombres) == 1:
            docente_nombre = nombres[0]
    # =======================================================================

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    page_w, page_h = landscape(A4)

    left, right, top, bottom = 1.2*cm, 1.2*cm, 1.4*cm, 1.2*cm
    title_h = 0.9*cm
    header_h = 1.0*cm
    y0 = page_h - top - title_h
    time_col_w = 3.2*cm
    grid_x0 = left + time_col_w
    grid_y_top = y0 - 0.4*cm
    grid_w = page_w - right - grid_x0
    grid_h = grid_y_top - bottom - header_h

    col_count = len(dias)
    row_count = len(bloques)
    col_w = grid_w / col_count
    row_h = grid_h / row_count

    # Título y subtítulo
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, page_h - top, "Horario semanal")
    c.setFont("Helvetica", 9)
    subt = [f"Período {periodo_id}", f"Cal {calendario_id}"]
    # Mostrar docente por nombre si aplica
    if docente_nombre:
        subt.append(f"Docente {docente_nombre}")
    else:
        # conserva otros filtros (sin cambiar ids)
        for p in ("grupo","ambiente"):
            v = request.query_params.get(p)
            if v:
                subt.append(f"{p.capitalize()} {v}")
    c.drawString(left, page_h - top - 0.6*cm, " · ".join(subt))

    # Encabezado de días
    c.setFont("Helvetica-Bold", 10)
    for i, d in enumerate(dias):
        label = DOW_LABEL.get(d, str(d))
        x_center = grid_x0 + i*col_w + col_w/2
        c.drawCentredString(x_center, grid_y_top - 0.75*cm + header_h - 0.65*cm, label)

    # Etiquetas de filas (rangos)
    c.setFont("Helvetica", 8)
    for r, b in enumerate(bloques):
        y_center = grid_y_top - header_h - r*row_h - row_h/2
        rango = f"{b.hora_inicio.strftime('%H:%M')} - {b.hora_fin.strftime('%H:%M')}"
        c.drawRightString(grid_x0 - 0.15*cm, y_center - 2.5, rango)

    # Grid
    c.setStrokeColor(colors.black); c.setLineWidth(1)
    for i in range(col_count + 1):
        x = grid_x0 + i * col_w
        c.line(x, grid_y_top - header_h - grid_h, x, grid_y_top - header_h)
    for r in range(row_count + 1):
        y = grid_y_top - header_h - r * row_h
        c.line(grid_x0, y, grid_x0 + grid_w, y)
    c.line(grid_x0, grid_y_top - header_h, grid_x0 + grid_w, grid_y_top - header_h)

    # Celdas de clases
    for cl in qs:
        if cl.bloque_inicio is None or cl.bloque_inicio.orden not in bloque_index:
            continue
        day_idx = dias.index(cl.day_of_week)
        start_idx = bloque_index[cl.bloque_inicio.orden]
        dur = int(cl.bloques_duracion or 1)

        x = grid_x0 + day_idx*col_w + 0.8
        y = grid_y_top - header_h - (start_idx + dur)*row_h + 0.8
        w = col_w - 1.6
        h = dur*row_h - 1.6

        fill = colors.Color(0.93,0.96,1.0) if cl.tipo == "T" else colors.Color(0.96,0.93,1.0)
        c.setFillColor(fill); c.setStrokeColor(colors.black)
        c.rect(x, y, w, h, stroke=1, fill=1)

        c.setFillColor(colors.black)
        top_pad, left_pad = 2.5, 3.0
        max_w = w - 2*left_pad

        a = cl.grupo.asignatura
        aula_txt = str(cl.ambiente) if cl.ambiente_id else "—"
        linea1 = f"{a.codigo} – {aula_txt}"
        linea2 = cl.grupo.codigo or f"Grupo #{cl.grupo_id}"

        lines1, size1 = _wrap_text(c, linea1, max_w, 2, base_size=8)
        lines2, size2 = _wrap_text(c, linea2, max_w, 1, base_size=7)
        yy = y + h - top_pad - size1
        c.setFont("Helvetica-Bold", size1)
        for L in lines1:
            c.drawString(x + left_pad, yy, L)
            yy -= size1 + 1.2
        c.setFont("Helvetica", size2)
        if yy - size2 > y + 1.5:
            c.drawString(x + left_pad, yy, lines2[0])

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="horario-semanal.pdf"'
    return resp
