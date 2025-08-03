To run the backend environment from within a VSCode Jupyter extension environment:

Have the Python extension installed in VSCode
Have already run poetry install in your project directory
Have ipykernel installed in your Poetry environment (if not, run poetry add ipykernel)

If the kernel still isn't showing up, you can install it manually from within your Poetry shell:
```
poetry shell
python -m ipykernel install --user --name=your-project-name
```

After doing this, you might need to reload VSCode (Command Palette → Developer: Reload Window) for the new kernel to appear in the kernel selector.
