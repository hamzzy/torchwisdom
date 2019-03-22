import torch
import random
from PIL import Image
import PIL
import collections
import torchvision.transforms.functional as F
import torchvision
from torchvision import transforms

__all__ = ['PairCompose','PairResize']

_pil_interpolation_to_str = {
    Image.NEAREST: 'PIL.Image.NEAREST',
    Image.BILINEAR: 'PIL.Image.BILINEAR',
    Image.BICUBIC: 'PIL.Image.BICUBIC',
    Image.LANCZOS: 'PIL.Image.LANCZOS',
    Image.HAMMING: 'PIL.Image.HAMMING',
    Image.BOX: 'PIL.Image.BOX',
}

class PairCompose(transforms.Compose):
    def __init__(self, transforms):
        super(PairCompose, self).__init__(transforms)

    def __call__(self, img1, img2):
        for t in self.transforms:
            img1, img2 = t(img1, img2)
        return img1, img2


class PairResize(transforms.Resize):
    def __init__(self, size, interpolation=Image.BILINEAR):
       super(PairResize, self).__init__(size, interpolation)

    def __call__(self, img1, img2):
        img1 = F.resize(img1, self.size, self.interpolation)
        img2 = F.resize(img2, self.size, self.interpolation)
        return img1, img2


class PairCenterCrop(transforms.CenterCrop):
    def __init__(self, size):
        super(PairCenterCrop, self).__init__(size)

    def __call__(self, img1, img2):
        img1 = F.center_crop(img1, self.size)
        img2 = F.center_crop(img2, self.size)
        return img1, img2


class PairPad(transforms.Pad):
    def __init__(self, padding, fill=0, padding_mode='constant'):
        super(PairPad, self).__init__(padding, fill, padding_mode)

    def __call__(self, img1, img2):
        img1 = F.pad(img1, self.padding, self.fill, self.padding_mode)
        img2 = F.pad(img2, self.padding, self.fill, self.padding_mode)
        return img1, img2


class PairRandomApply(transforms.RandomApply):
    def __init__(self,  transforms, p=0.5):
        super(PairRandomApply, self).__init__(transforms, p)

    def __call__(self, img1, img2):
        if self.p < random.random():
            return img1, img2
        for t in self.transforms:
            img1 = t(img1)
            img2 = t(img2)
        return img1, img2


class PairRandomCrop(transforms.RandomCrop):
    def __init__(self, size, padding=None, pad_if_needed=False, fill=0, padding_mode='constant'):
        super(PairRandomCrop, self).__init__(size, padding, pad_if_needed, fill, padding_mode)

    def __call__(self, img1, img2):
        img1 = self._crop(img1)
        img2 = self._crop(img2)
        return img1, img2

    def _crop(self, img):
        """
                Args:
                    img (PIL Image): Image to be cropped.
                Returns:
                    PIL Image: Cropped image.
                """
        if self.padding is not None:
            img = F.pad(img, self.padding, self.fill, self.padding_mode)

        # pad the width if needed
        if self.pad_if_needed and img.size[0] < self.size[1]:
            img = F.pad(img, (self.size[1] - img.size[0], 0), self.fill, self.padding_mode)
        # pad the height if needed
        if self.pad_if_needed and img.size[1] < self.size[0]:
            img = F.pad(img, (0, self.size[0] - img.size[1]), self.fill, self.padding_mode)

        i, j, h, w = self.get_params(img, self.size)

        return F.crop(img, i, j, h, w)


class PairRandomHorizontalFlip(transforms.RandomHorizontalFlip):
    def __init__(self, p=0.5):
        super(PairRandomHorizontalFlip, self).__init__(p)

    def __call__(self, img1, img2):
        if random.random() < self.p:
            img1 = F.hflip(img1)
            img2 = F.hflip(img2)
        return img1, img2

class PairRandomVerticalFlip(transforms.RandomVerticalFlip):
    def __init__(self, p=0.5):
        super(PairRandomHorizontalFlip, self).__init__(p)

    def __call__(self, img1, img2):
        if random.random() < self.p:
            img1 = F.vflip(img1)
            img2 = F.vflip(img2)
        return img1, img2


class PairRandomResizedCrop(transforms.RandomResizedCrop):
    def __init__(self, size, scale=(0.08, 1.0), ratio=(3. / 4., 4. / 3.), interpolation=Image.BILINEAR):
        super(PairRandomResizedCrop, self).__init__(size, scale, ratio, interpolation)

    def __call__(self, img1, img2):
        i1, j1, h1, w1 = self.get_params(img1, self.scale, self.ratio)
        img1 = F.resized_crop(img1, i1, j1, h1, w1, self.size, self.interpolation)

        i2, j2, h2, w2 = self.get_params(img2, self.scale, self.ratio)
        img2 = F.resized_crop(img2, i2, j2, h2, w2, self.size, self.interpolation)

        return img1, img2

