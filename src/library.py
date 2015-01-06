
with open("module1/module.py") as f:
	code = compile(f.read(), "module.py", 'exec')
	local = {
		'env': 'Hello World'
	}
	exec(code, globals(), local)
	#print(local)

	local['initialize']("Hello World!")

