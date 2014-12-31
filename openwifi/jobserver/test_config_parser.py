import uci 
myuci = uci.Uci()
cfile=open('example_config')
myuci.load_tree(cfile.read())
print(myuci.export_tree())
