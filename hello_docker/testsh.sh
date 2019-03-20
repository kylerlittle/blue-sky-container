echo "In the shell script"
python hi.py
echo "exiting the container"
echo "testing fortran compiler/run"
gfortran ftest.f90
./a.out
echo "fortran run"
#htop #you can see the output by doing docker run -it imagename
echo "finished the script"
/bin/bash
