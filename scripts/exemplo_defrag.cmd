# Exemplo de defrag: compara INIT, END e OPT a partir do mesmo estado.
# Cada bloco abaixo reinicia a memória para repetir o estado do enunciado:
# id=1 @0 +10B, buraco @10 +54B, id=3 @18 +6B.
init 64
alloc 10 first
alloc 8 first
alloc 6 first
freeid 2
show
defrag init

init 64
alloc 10 first
alloc 8 first
alloc 6 first
freeid 2
defrag end

init 64
alloc 10 first
alloc 8 first
alloc 6 first
freeid 2
defrag opt
show
stats
EOF
