' Punto de entrada recomendado de Agente Laboral Gen -- doble click, sin
' consola. Unico proposito: encontrar un interprete de Python capaz de
' correr scripts .pyw (ventana grafica, sin consola) y lanzar
' Abrir_Agente_Laboral_Gen.pyw con el, sin depender de que Windows tenga
' asociada la extension .pyw a ningun programa (los .vbs si estan
' asociados a wscript.exe por defecto en Windows).
'
' No toca el registro, no pide permisos de administrador, no postula, no
' guarda el CV ni agrega historial -- solo lanza el .pyw, que es quien
' hace ese trabajo (ver Abrir_Agente_Laboral_Gen.pyw).

Option Explicit

Dim objShell, objFSO, scriptDir, pywScript
Dim comandos(2), i, lanzado

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = scriptDir

pywScript = """" & scriptDir & "\Abrir_Agente_Laboral_Gen.pyw" & """"

' Orden de intentos: pyw.exe (lanzador oficial "windowed") primero, despues
' py.exe -3w (selector de version del launcher, tambien windowed), y por
' ultimo pythonw.exe directo. WindowStyle 0 = oculta cualquier ventana de
' consola que alguno de estos pudiera llegar a crear.
comandos(0) = "pyw.exe " & pywScript
comandos(1) = "py.exe -3w " & pywScript
comandos(2) = "pythonw.exe " & pywScript

lanzado = False

For i = 0 To UBound(comandos)
    On Error Resume Next
    Err.Clear
    objShell.Run comandos(i), 0, False
    If Err.Number = 0 Then
        lanzado = True
    End If
    On Error Goto 0
    If lanzado Then Exit For
Next

If Not lanzado Then
    MsgBox "No se encontro Python. Instala Python 3.11 o superior desde" & vbCrLf & _
        "python.org y volve a abrir este archivo.", vbExclamation, "Agente Laboral Gen"
End If
