import subprocess
import sys
import pytest
from buscador.cli import main
from conftest import RAIZ, REPO_DEMO


def test_buscar_por_archivo_y_nombre(capsys):
    assert main(["--dir", str(REPO_DEMO), "--funcion", "estadisticas.py:contar_pares", "--top", "2"]) == 0
    salida = capsys.readouterr().out
    assert "copiado/estadisticas_v2.py:21" in salida and "cuantos_pares" in salida
    assert salida.count("\n   ") >= 2   # dos filas de resultados


def test_buscar_pegando_el_codigo(capsys):
    codigo = "def f(m):\n    if m <= 1:\n        return 1\n    return m * f(m - 1)"
    assert main(["--dir", str(REPO_DEMO), "--codigo", codigo, "--top", "2"]) == 0
    salida = capsys.readouterr().out
    assert "<codigo pegado>" in salida
    assert "factorial" in salida and "fact" in salida   # el original y su clon, ambos con score 1


def test_mostrar_normalizado(capsys):
    main(["--dir", str(REPO_DEMO), "--funcion", "estadisticas.py:promedio", "--mostrar-normalizado"])
    salida = capsys.readouterr().out
    assert "numeros -> VAR1" in salida and "def FUNC(VAR1):" in salida


def test_reporte_de_duplicados(capsys):
    assert main(["--dir", str(REPO_DEMO), "--duplicados"]) == 0
    salida = capsys.readouterr().out
    assert "varianza" in salida and "calcular_varianza" in salida


def test_funcion_inexistente_devuelve_error(capsys):
    assert main(["--dir", str(REPO_DEMO), "--funcion", "estadisticas.py:nada"]) == 2
    assert "No hay una función 'nada'" in capsys.readouterr().err


def test_funcion_en_archivo_que_no_parsea_devuelve_error(capsys):
    ruta = str(REPO_DEMO / "legacy_py2.py")
    assert main(["--dir", str(REPO_DEMO), "--funcion", f"{ruta}:saludar"]) == 2
    assert "No se pudo parsear" in capsys.readouterr().err


def test_archivo_fuera_del_repositorio(tmp_path, capsys):
    externo = tmp_path / "externo.py"
    externo.write_text("def g(ys):\n    t = 0\n    for y in ys:\n        t += y\n    return t / len(ys)\n",
                       encoding="utf-8")
    assert main(["--dir", str(REPO_DEMO), "--funcion", f"{externo}:g", "--top", "1"]) == 0
    salida = capsys.readouterr().out
    # empata en 1.0 con promedio(); el desempate por ruta pone primero copiado/...
    assert "1.000" in salida and "media_aritmetica" in salida


def test_directorio_inexistente_devuelve_error(tmp_path, capsys):
    assert main(["--dir", str(tmp_path / "no_existe"), "--funcion", "a.py:f"]) == 2
    assert "No es un directorio" in capsys.readouterr().err


@pytest.mark.parametrize("argumentos", [["--top", "0"], ["--umbral", "1.5"], ["-n", "0"]])
def test_argumentos_invalidos(argumentos):
    with pytest.raises(SystemExit) as e:
        main(["--dir", str(REPO_DEMO), "--funcion", "estadisticas.py:promedio", *argumentos])
    assert e.value.code == 2


def test_script_ejecutable_como_en_el_enunciado():
    proceso = subprocess.run(
        [sys.executable, "buscar_similares.py", "--dir", "ejemplos/repo_demo",
         "--funcion", "estadisticas.py:promedio", "--top", "5"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proceso.returncode == 0
    assert "media_aritmetica" in proceso.stdout
    assert "legacy_py2.py" in proceso.stderr     # aviso del archivo Python 2 omitido
