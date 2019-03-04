echo "In the shell script"
echo "running C code"
gcc cTest.c -o theCode.o
./theCode.o
echo "running python code"
python hi.py
echo "running fortran code"
gfortran fortranTest.f90
./a.out
echo "finished the script"
echo "exiting the container"

