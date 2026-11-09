"""
Fusiona series DUPLICADAS: mas de una fila con el mismo `(fuente, slug)`.

Motivo: el scraper creo la misma serie dos veces. Casos vivos al 15-Oct-2026:
370/372 (`tempal-item-no-chikara`, 27-Sep 19:48 y 20:02) y 371/373
(`tensei-kizoku-kantei-skill-de-nariagaru-3rd-season`, misma ventana). Como la
carpeta de descarga es funcion pura de `(fuente, slug)`, las dos filas resuelven
al MISMO `Episodio-N.mp4`: la que llega segunda recibe "Ya existe" para siempre.
Prefijar por fuente (ver `series.paths`) NO alcanza para este caso, porque la
fuente es la misma. Deduplicar es la unica salida.

Que hace, por cada grupo con mas de una fila:
  - Elige ganadora: la de mas capitulos; empate -> la marcada favorita; empate
    -> el id mas bajo (la fila mas vieja).
  - Por cada capitulo de la perdedora: si la ganadora ya tiene ese `numero`,
    fusiona `ultimo_segundo` (se conserva el mayor) y borra el de la perdedora;
    si la ganadora no lo tiene, reapunta el capitulo a la ganadora.
  - Borra la fila perdedora (sus capitulos caen por CASCADE).

Garantias:
  - Por defecto NO modifica nada: hay que pasar `--apply` de forma explicita.
  - Idempotente: sin duplicados no hace nada, y correrlo dos veces es inocuo.
  - Reporta las portadas que quedan huerfanas en `media/portadas/`: Django no
    borra los archivos de un `ImageField` al borrar la fila.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from series.models import Serie


class Command(BaseCommand):
    help = (
        'Fusiona series duplicadas (misma fuente y slug en mas de una fila). '
        'Por defecto solo imprime el plan; usa --apply para aplicarlo.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplica la fusion. Sin este flag el comando no modifica nada.',
        )

    def handle(self, *args, **options):
        aplicar = options['apply']

        grupos = {}
        for serie in Serie.objects.only('id', 'slug', 'fuente'):
            grupos.setdefault((serie.fuente, serie.slug), []).append(serie)

        duplicados = {clave: filas for clave, filas in grupos.items() if len(filas) > 1}
        if not duplicados:
            self.stdout.write(self.style.SUCCESS('No hay series duplicadas. Nada que hacer.'))
            return

        if not aplicar:
            self.stdout.write(self.style.WARNING('MODO PLAN (no se modifica nada). Usa --apply para aplicar.'))

        fusionadas = reapuntados = borrados = 0
        portadas_huerfanas = []

        for (fuente, slug), filas in sorted(duplicados.items()):
            with transaction.atomic():
                ganadora = self._elegir_ganadora(filas)
                perdedoras = [s for s in filas if s.pk != ganadora.pk]

                self.stdout.write('')
                self.stdout.write(f'[grupo] fuente={fuente} slug={slug}')
                self.stdout.write(
                    f'  ganadora:  id={ganadora.pk} capitulos={ganadora.capitulos.count()} '
                    f'favorita={ganadora.favorito}'
                )

                for perdedora in perdedoras:
                    self.stdout.write(
                        f'  perdedora: id={perdedora.pk} capitulos={perdedora.capitulos.count()} '
                        f'favorita={perdedora.favorito} portada={perdedora.portada.name or "(sin portada)"}'
                    )
                    if perdedora.portada:
                        portadas_huerfanas.append(perdedora.portada.name)

                    for cap in list(perdedora.capitulos.all()):
                        gemelo = ganadora.capitulos.filter(numero=cap.numero).first()
                        if gemelo is None:
                            self.stdout.write(
                                f'    cap id={cap.pk} num={cap.numero}: la ganadora no lo tiene -> se reapunta'
                            )
                            reapuntados += 1
                            if aplicar:
                                cap.serie = ganadora
                                cap.save(update_fields=['serie'])
                        else:
                            mayor = max(gemelo.ultimo_segundo, cap.ultimo_segundo)
                            self.stdout.write(
                                f'    cap id={cap.pk} num={cap.numero}: gemelo id={gemelo.pk} '
                                f'({gemelo.ultimo_segundo}s vs {cap.ultimo_segundo}s -> {mayor}s) -> se borra el duplicado'
                            )
                            borrados += 1
                            if aplicar:
                                if mayor != gemelo.ultimo_segundo:
                                    gemelo.ultimo_segundo = mayor
                                    gemelo.save(update_fields=['ultimo_segundo'])
                                cap.delete()

                    fusionadas += 1
                    if aplicar:
                        if perdedora.favorito and not ganadora.favorito:
                            ganadora.favorito = True
                            ganadora.save(update_fields=['favorito'])
                        perdedora.delete()

        self.stdout.write('')
        verbo = 'aplicado' if aplicar else 'planificado'
        self.stdout.write(self.style.SUCCESS(
            f'{verbo}: {fusionadas} series fusionadas, {reapuntados} capitulos reapuntados, '
            f'{borrados} capitulos duplicados borrados'
        ))
        if portadas_huerfanas:
            self.stdout.write('Portadas que quedan en disco sin serie duena (borralas a mano si queres):')
            for nombre in portadas_huerfanas:
                self.stdout.write(f'  - {nombre}')

    @staticmethod
    def _elegir_ganadora(filas):
        """Mas capitulos; empate -> favorita; empate -> id mas bajo (la mas vieja)."""
        return max(filas, key=lambda s: (s.capitulos.count(), 1 if s.favorito else 0, -s.pk))
